"""
Nutrition Controller - Web adapter for the health manager.

Handles API endpoints and web views for:
- User profiles
- Meal analysis (vision + nutrition)
- Dashboard data
- RAG chat
"""

import os
import uuid
import json
from flask import request, jsonify, render_template, Response, stream_with_context
from src.application.profile_use_cases import (
    CreateProfileUseCase, GetProfilesUseCase,
    GetProfileByIdUseCase, UpdateProfileUseCase,
)
from src.application.meal_use_cases import (
    AnalyzeMealUseCase, GetMealHistoryUseCase, GetTodaySummaryUseCase,
)
from src.application.chat_use_case import ChatUseCase


UPLOAD_DIR = os.path.join("static", "uploads")


class NutritionController:

    def __init__(
        self,
        create_profile: CreateProfileUseCase,
        get_profiles: GetProfilesUseCase,
        get_profile_by_id: GetProfileByIdUseCase,
        update_profile: UpdateProfileUseCase,
        analyze_meal: AnalyzeMealUseCase,
        get_meal_history: GetMealHistoryUseCase,
        get_today_summary: GetTodaySummaryUseCase,
        chat: ChatUseCase,
    ):
        self.create_profile_uc = create_profile
        self.get_profiles_uc = get_profiles
        self.get_profile_by_id_uc = get_profile_by_id
        self.update_profile_uc = update_profile
        self.analyze_meal_uc = analyze_meal
        self.get_meal_history_uc = get_meal_history
        self.get_today_summary_uc = get_today_summary
        self.chat_uc = chat

        os.makedirs(UPLOAD_DIR, exist_ok=True)

    # ── Web Views ───────────────────────────────────────────────────

    def dashboard_view(self):
        """GET /web/dashboard - Main SPA dashboard"""
        return render_template('dashboard.html')

    # ── Profiles API ────────────────────────────────────────────────

    def api_create_profile(self):
        """POST /api/profiles"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400
        result = self.create_profile_uc.execute(
            name=data.get('name', ''),
            age=data.get('age', 0),
            weight=data.get('weight', 0),
            height=data.get('height', 0),
            goal=data.get('goal', 'maintenance'),
            daily_calories=data.get('daily_calories', 2000),
            daily_protein=data.get('daily_protein', 75),
            daily_carbs=data.get('daily_carbs', 250),
            daily_fat=data.get('daily_fat', 65),
            allergies=data.get('allergies', ''),
        )
        return jsonify(result), 201 if result['success'] else 400

    def api_get_profiles(self):
        """GET /api/profiles"""
        result = self.get_profiles_uc.execute()
        return jsonify(result), 200 if result['success'] else 500

    def api_get_profile(self, profile_id: int):
        """GET /api/profiles/<id>"""
        result = self.get_profile_by_id_uc.execute(profile_id)
        return jsonify(result), 200 if result['success'] else 404

    def api_update_profile(self, profile_id: int):
        """PUT /api/profiles/<id>"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400
        result = self.update_profile_uc.execute(profile_id, **data)
        return jsonify(result), 200 if result['success'] else 400

    # ── Meals API ───────────────────────────────────────────────────

    def api_analyze_meal(self):
        """POST /api/meals/analyze  (multipart form: profile_id + image file + optional comment)"""
        profile_id = request.form.get('profile_id')
        if not profile_id:
            return jsonify({'success': False, 'error': 'profile_id required'}), 400

        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'error': 'Image file required'}), 400

        comment = request.form.get('comment', '').strip()

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)

        result = self.analyze_meal_uc.execute(int(profile_id), filepath, comment=comment)
        return jsonify(result), 200 if result['success'] else 400

    def api_meal_history(self, profile_id: int):
        """GET /api/meals/<profile_id>"""
        limit = request.args.get('limit', 20, type=int)
        result = self.get_meal_history_uc.execute(profile_id, limit)
        return jsonify(result), 200 if result['success'] else 500

    def api_today_summary(self, profile_id: int):
        """GET /api/dashboard/<profile_id>"""
        result = self.get_today_summary_uc.execute(profile_id)
        return jsonify(result), 200 if result['success'] else 400

    # ── Chat API ────────────────────────────────────────────────────

    def api_chat(self):
        """POST /api/chat  {profile_id, message}"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400

        profile_id = data.get('profile_id')
        message = data.get('message', '')

        if not profile_id:
            return jsonify({'success': False, 'error': 'profile_id required'}), 400

        result = self.chat_uc.execute(int(profile_id), message)
        return jsonify(result), 200 if result['success'] else 400

    def api_chat_stream(self):
        """
        POST /api/chat/stream {profile_id, message}
        Returns a Server-Sent Events (SSE) stream with progress updates and final response.
        """
        import queue
        import threading

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400

        profile_id = data.get('profile_id')
        message = data.get('message', '')

        if not profile_id:
            return jsonify({'success': False, 'error': 'profile_id required'}), 400

        q = queue.Queue()

        def on_progress(event):
            # Accept both plain strings (legacy) and structured dicts (new)
            if isinstance(event, dict):
                step_type = event.get('type', 'thinking')
                q.put({
                    'type': 'step',
                    'step_type': step_type,
                    'label': event.get('label', ''),
                    'detail': str(event.get('detail', '')),
                })
            else:
                q.put({'type': 'step', 'step_type': 'thinking', 'label': str(event), 'detail': ''})

        def run_use_case():
            try:
                result = self.chat_uc.execute(int(profile_id), message, on_progress=on_progress)
                if result['success']:
                    q.put({'type': 'final', 'text': result['data']['response']})
                else:
                    q.put({'type': 'error', 'text': result.get('error', 'Chat error')})
            except Exception as e:
                q.put({'type': 'error', 'text': str(e)})
            finally:
                q.put(None)  # Signal end of stream

        threading.Thread(target=run_use_case).start()

        def generate():
            while True:
                item = q.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    def api_chat_history(self, profile_id: int):
        """GET /api/chat/<profile_id>"""
        result = self.chat_uc.get_history(profile_id)
        return jsonify(result), 200 if result['success'] else 500

    def api_chat_clear(self, profile_id: int):
        """DELETE /api/chat/<profile_id>"""
        result = self.chat_uc.clear_history(profile_id)
        return jsonify(result), 200 if result['success'] else 500

