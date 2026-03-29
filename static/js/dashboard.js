/* ═══════════════════════════════════════════════════════════════ */
/*                     STATE & INITIALIZATION                     */
/* ═══════════════════════════════════════════════════════════════ */
let currentProfileId = null;
let donutChart = null;
let selectedFile = null;
let cameraStream = null;

const STEP_ICONS = {
    thinking:     '🧠',
    tool_start:   '🔧',
    tool_end:     '✅',
    synthesizing: '✍️',
};

document.addEventListener('DOMContentLoaded', () => {
    loadProfiles();
    fetchModels('chat');
    fetchModels('vision');
});

/* ═══════════════════════════════════════════════════════════════ */
/*                         TAB NAVIGATION                         */
/* ═══════════════════════════════════════════════════════════════ */
function showTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
    if (btn) btn.classList.add('active');
    document.getElementById('tab-' + name).classList.add('active');

    if (name === 'dashboard' && currentProfileId) loadDashboard();
    if (name === 'history' && currentProfileId) loadHistory();
    if (name === 'chat' && currentProfileId) loadChatHistory();
}

/* ═══════════════════════════════════════════════════════════════ */
/*                          PROFILES                              */
/* ═══════════════════════════════════════════════════════════════ */
async function loadProfiles() {
    const res = await fetch('/api/profiles');
    const data = await res.json();
    const sel = document.getElementById('profileSelect');
    sel.innerHTML = '<option value="">-- Seleccionar perfil --</option>';
    if (data.success && data.data.length) {
        data.data.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (${p.goal === 'deficit' ? '⬇️' : p.goal === 'muscle_gain' ? '💪' : '⚖️'} ${p.daily_calories}kcal)`;
            sel.appendChild(opt);
        });
        // Auto-select first
        if (!currentProfileId && data.data.length) {
            sel.value = data.data[0].id;
            onProfileChange();
        }
    }
}

function onProfileChange() {
    const id = document.getElementById('profileSelect').value;
    currentProfileId = id ? parseInt(id) : null;
    const info = document.getElementById('profileInfo');

    const panels = ['dash', 'meal', 'history', 'chat'];

    if (currentProfileId) {
        info.textContent = '✅ Perfil activo';
        panels.forEach(p => {
            document.getElementById(`noprofile-${p}`).classList.add('hidden');
            document.getElementById(`${p}-content`).classList.remove('hidden');
        });
        loadDashboard();
        loadProfileIntoForm(currentProfileId);
        resetChatUI();
        loadChatHistory();
        loadHistory();
    } else {
        info.textContent = '';
        panels.forEach(p => {
            document.getElementById(`noprofile-${p}`).classList.remove('hidden');
            document.getElementById(`${p}-content`).classList.add('hidden');
        });
    }
}

function resetChatUI() {
    const container = document.getElementById('chatMessages');
    const typing = document.getElementById('chatTyping');
    container.innerHTML = `
<div class="chat-msg assistant">
    <p>👋 ¡Hola! Soy tu agente de nutrición. ¿En qué puedo ayudarte?</p>
</div>`;
    container.appendChild(typing);
    _lastChatDate = '';
}

async function saveProfile(e) {
    e.preventDefault();
    const id = document.getElementById('pf-id').value;
    const body = {
        name: document.getElementById('pf-name').value,
        age: parseInt(document.getElementById('pf-age').value),
        weight: parseFloat(document.getElementById('pf-weight').value),
        height: parseFloat(document.getElementById('pf-height').value),
        goal: document.getElementById('pf-goal').value,
        daily_calories: parseInt(document.getElementById('pf-calories').value),
        daily_protein: parseFloat(document.getElementById('pf-protein').value),
        daily_carbs: parseFloat(document.getElementById('pf-carbs').value),
        daily_fat: parseFloat(document.getElementById('pf-fat').value),
        allergies: document.getElementById('pf-allergies').value,
    };
    const url = id ? `/api/profiles/${id}` : '/api/profiles';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (data.success) {
        showAlert('profileAlert', `✅ Perfil ${id ? 'actualizado' : 'creado'}: ${data.data.name}`, 'success');
        await loadProfiles();
        document.getElementById('profileSelect').value = data.data.id;
        onProfileChange();
    } else {
        showAlert('profileAlert', '❌ ' + data.error, 'error');
    }
}

async function loadProfileIntoForm(pid) {
    const res = await fetch(`/api/profiles/${pid}`);
    const data = await res.json();
    if (data.success) {
        const p = data.data;
        document.getElementById('pf-id').value = p.id;
        document.getElementById('pf-name').value = p.name;
        document.getElementById('pf-age').value = p.age;
        document.getElementById('pf-weight').value = p.weight;
        document.getElementById('pf-height').value = p.height;
        document.getElementById('pf-goal').value = p.goal;
        document.getElementById('pf-calories').value = p.daily_calories;
        document.getElementById('pf-protein').value = p.daily_protein;
        document.getElementById('pf-carbs').value = p.daily_carbs;
        document.getElementById('pf-fat').value = p.daily_fat;
        document.getElementById('pf-allergies').value = p.allergies;
        document.getElementById('profileFormTitle').textContent = '✏️ Editar Perfil';
    }
}

function resetProfileForm() {
    document.getElementById('pf-id').value = '';
    document.getElementById('profileForm').reset();
    document.getElementById('profileFormTitle').textContent = '➕ Crear Perfil';
}

/* ═══════════════════════════════════════════════════════════════ */
/*                          DASHBOARD                             */
/* ═══════════════════════════════════════════════════════════════ */
async function loadDashboard() {
    if (!currentProfileId) return;
    const res = await fetch(`/api/dashboard/${currentProfileId}`);
    const data = await res.json();
    if (!data.success) return;

    const { consumed, goals, meals_today, meals } = data.data;
    const pct = (v, g) => g > 0 ? Math.min(Math.round(v / g * 100), 100) : 0;

    document.getElementById('d-cal').textContent = Math.round(consumed.calories);
    document.getElementById('d-cal-sub').textContent = `de ${goals.calories} kcal`;
    document.getElementById('d-cal-bar').style.width = pct(consumed.calories, goals.calories) + '%';

    document.getElementById('d-prot').textContent = Math.round(consumed.protein) + 'g';
    document.getElementById('d-prot-sub').textContent = `de ${goals.protein}g`;
    document.getElementById('d-prot-bar').style.width = pct(consumed.protein, goals.protein) + '%';

    document.getElementById('d-carbs').textContent = Math.round(consumed.carbs) + 'g';
    document.getElementById('d-carbs-sub').textContent = `de ${goals.carbs}g`;
    document.getElementById('d-carbs-bar').style.width = pct(consumed.carbs, goals.carbs) + '%';

    document.getElementById('d-fat').textContent = Math.round(consumed.fat) + 'g';
    document.getElementById('d-fat-sub').textContent = `de ${goals.fat}g`;
    document.getElementById('d-fat-bar').style.width = pct(consumed.fat, goals.fat) + '%';

    document.getElementById('meals-count').textContent = meals_today;

    // Donut chart
    updateDonut(consumed, goals);

    // Today's meals list
    const list = document.getElementById('dash-meals-list');
    const empty = document.getElementById('dash-meals-empty');
    if (meals && meals.length) {
        empty.classList.add('hidden');
        list.innerHTML = meals.map(m => mealCardHTML(m)).join('');
    } else {
        list.innerHTML = '';
        empty.classList.remove('hidden');
    }
}

function updateDonut(consumed, goals) {
    const ctx = document.getElementById('donutChart').getContext('2d');
    const prot = consumed.protein;
    const carbs = consumed.carbs;
    const fat = consumed.fat;
    const remaining = Math.max(0, goals.calories - consumed.calories);

    if (donutChart) donutChart.destroy();
    donutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [`Proteínas ${Math.round(prot)}g`, `Carbos ${Math.round(carbs)}g`, `Grasas ${Math.round(fat)}g`, 'Restante'],
            datasets: [{
                data: [prot * 4, carbs * 4, fat * 9, remaining],
                backgroundColor: ['#ef4444', '#6366f1', '#eab308', '#f1f5f9'],
                borderWidth: 2,
                borderColor: '#fff',
            }]
        },
        options: {
            responsive: true,
            cutout: '65%',
            plugins: {
                legend: { position: 'bottom', labels: { padding: 15, font: { size: 12 } } },
                tooltip: {
                    callbacks: {
                        label: (c) => ` ${c.label}: ${Math.round(c.raw)} kcal`
                    }
                }
            }
        }
    });
}

/* ═══════════════════════════════════════════════════════════════ */
/*                      MEAL ANALYSIS                             */
/* ═══════════════════════════════════════════════════════════════ */
const imageInput = document.getElementById('imageInput');
const imagePreview = document.getElementById('imagePreview');
const uploadArea = document.getElementById('uploadArea');

imageInput.addEventListener('change', (e) => {
    if (e.target.files[0]) setImageFile(e.target.files[0]);
});

uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', (e) => {
    e.preventDefault(); uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files[0]) setImageFile(e.dataTransfer.files[0]);
});

function setImageFile(file) {
    selectedFile = file;
    const url = URL.createObjectURL(file);
    imagePreview.src = url;
    imagePreview.style.display = 'block';
    document.getElementById('analyzeBtn').classList.remove('hidden');
    document.getElementById('commentWrapper').classList.remove('hidden');
}

async function analyzeMeal() {
    if (!currentProfileId) { showAlert('alertGlobal', '⚠️ Seleccioná un perfil primero', 'error'); return; }
    if (!selectedFile) return;

    document.getElementById('analyzeBtn').classList.add('hidden');
    document.getElementById('mealUploadCard').classList.add('hidden');
    document.getElementById('analyzeLoading').classList.remove('hidden');
    document.getElementById('analysisResult').style.display = 'none';
    document.getElementById('analysisEmpty').style.display = 'none';

    resetMealThinkingPanel();

    const form = new FormData();
    form.append('profile_id', currentProfileId);
    form.append('image', selectedFile);
    const comment = document.getElementById('mealComment').value.trim();
    if (comment) form.append('comment', comment);

    try {
        const response = await fetch('/api/meals/analyze/stream', {
            method: 'POST',
            body: form
        });

        if (!response.ok) throw new Error('Error en la respuesta del servidor');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.type === 'step') {
                            addMealThinkingStep(data.step_type || 'thinking', data.label || '', data.detail || '');
                        } else if (data.type === 'final') {
                            markMealThinkingDone();
                            setTimeout(() => {
                                document.getElementById('analyzeLoading').classList.add('hidden');
                                document.getElementById('mealUploadCard').classList.remove('hidden');
                                showAnalysisResult(data.data);
                                loadDashboard();
                                document.getElementById('mealComment').value = '';
                                document.getElementById('commentWrapper').classList.add('hidden');
                            }, 800);
                        } else if (data.type === 'error') {
                            document.getElementById('analyzeLoading').classList.add('hidden');
                            document.getElementById('mealUploadCard').classList.remove('hidden');
                            document.getElementById('analyzeBtn').classList.remove('hidden');
                            showAlert('alertGlobal', '❌ ' + data.text, 'error');
                        }
                    } catch (e) {
                        console.error('Error parseando SSE (meal):', e, line);
                    }
                }
            }
        }
    } catch (err) {
        document.getElementById('analyzeLoading').classList.add('hidden');
        document.getElementById('mealUploadCard').classList.remove('hidden');
        document.getElementById('analyzeBtn').classList.remove('hidden');
        showAlert('alertGlobal', '❌ Error de conexión: ' + err.message, 'error');
    }
}

function resetMealThinkingPanel() {
    document.getElementById('mealThinkingSteps').innerHTML = '';
    document.getElementById('mealThinkingSteps').classList.add('hidden');
    document.getElementById('mealThLabel').textContent = 'Analizando comida...';
    const header = document.getElementById('mealThinkingHeader');
    header.classList.remove('has-steps', 'collapsed');
    const spinner = document.getElementById('mealThSpinner');
    spinner.className = 'th-spinner';
    spinner.textContent = '';
    document.getElementById('mealThToggle').style.display = 'none';
}

function addMealThinkingStep(stepType, label, detail) {
    const steps = document.getElementById('mealThinkingSteps');
    steps.classList.remove('hidden');
    document.getElementById('mealThinkingHeader').classList.add('has-steps');
    document.getElementById('mealThToggle').style.display = '';

    const icon = STEP_ICONS[stepType] || '💬';
    const step = document.createElement('div');
    step.className = `thinking-step type-${stepType}`;
    step.innerHTML = `
        <span class="step-icon">${icon}</span>
        <div class="step-body">
            <div class="step-label">${esc(label)}</div>
            ${detail ? `<div class="step-detail">${esc(String(detail).substring(0, 80))}</div>` : ''}
        </div>`;
    steps.appendChild(step);
    steps.scrollTop = steps.scrollHeight;

    document.getElementById('mealThLabel').textContent = label;
}

function markMealThinkingDone() {
    const spinner = document.getElementById('mealThSpinner');
    spinner.className = 'th-check';
    spinner.textContent = '✓';
    document.getElementById('mealThLabel').textContent = 'Análisis completado';
    setTimeout(() => {
        document.getElementById('mealThinkingHeader').classList.add('collapsed');
        document.getElementById('mealThinkingSteps').classList.add('hidden');
    }, 800);
}

function toggleMealThinking() {
    const header = document.getElementById('mealThinkingHeader');
    const steps = document.getElementById('mealThinkingSteps');
    header.classList.toggle('collapsed');
    steps.classList.toggle('hidden');
}

function showAnalysisResult(data) {
    const meal = data.data;

    // Show analyzed photo in result panel
    const analysisPhoto = document.getElementById('analysisPhoto');
    if (meal.photo_path) {
        analysisPhoto.src = '/' + meal.photo_path;
        analysisPhoto.style.display = 'block';
    } else {
        analysisPhoto.style.display = 'none';
    }

    document.getElementById('analysisDesc').textContent = '✅ ' + meal.description;
    document.getElementById('a-cal').textContent = Math.round(meal.total_calories);
    document.getElementById('a-prot').textContent = Math.round(meal.total_protein) + 'g';
    document.getElementById('a-carbs').textContent = Math.round(meal.total_carbs) + 'g';
    document.getElementById('a-fat').textContent = Math.round(meal.total_fat) + 'g';

    const foodsDiv = document.getElementById('analysisFoods');
    const items = meal.food_items || [];
    foodsDiv.innerHTML = items.map(f => `
<div class="food-item">
    <span class="fi-name">${esc(f.name)} (${f.quantity}${f.unit})</span>
    <span class="fi-macros">${Math.round(f.estimated_calories || 0)}kcal · P:${Math.round(f.estimated_protein || 0)}g · C:${Math.round(f.estimated_carbs || 0)}g · G:${Math.round(f.estimated_fat || 0)}g</span>
</div>
`).join('');

    let sourceText = '🤖 Estimación por IA (Vision)';
    if (data.enriched_with === 'usda_fdc') sourceText = '✅ USDA FDC API';
    if (data.enriched_with === 'nutrition_label_ocr') sourceText = '🏷️ Etiqueta Nutricional (OCR)';
    document.getElementById('analysisSource').textContent = `Fuente de datos: ${sourceText}`;

    document.getElementById('analysisResult').style.display = 'block';

    // Reset upload area for a new image
    imagePreview.style.display = 'none';
    imagePreview.src = '';
    imageInput.value = '';
    document.getElementById('analyzeBtn').classList.add('hidden');
    selectedFile = null;
}

/* ═══════════════════════════════════════════════════════════════ */
/*                       MEAL HISTORY                             */
/* ═══════════════════════════════════════════════════════════════ */
async function loadHistory() {
    if (!currentProfileId) return;
    const res = await fetch(`/api/meals/${currentProfileId}?limit=30`);
    const data = await res.json();
    const list = document.getElementById('historyList');
    const empty = document.getElementById('historyEmpty');

    if (data.success && data.data.length) {
        empty.style.display = 'none';

        // Group meals by date
        const groups = {};
        data.data.forEach(m => {
            const dateKey = m.created_at ? m.created_at.split('T')[0] : 'Desconocido';
            if (!groups[dateKey]) groups[dateKey] = [];
            groups[dateKey].push(m);
        });

        const sortedDates = Object.keys(groups).sort().reverse();
        let html = '';

        sortedDates.forEach(dateKey => {
            html += `<div class="history-date-group">📅 ${formatDateGroup(dateKey)}</div>`;
            html += groups[dateKey].map(m => mealCardHTML(m)).join('');
        });

        list.innerHTML = html;
    } else {
        list.innerHTML = '';
        empty.style.display = 'block';
    }
}

function formatDateGroup(dateStr) {
    if (dateStr === 'Desconocido') return 'Sin fecha';
    const d = new Date(dateStr + 'T12:00:00'); // Midday to avoid TZ shifts
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

    if (sameDay(d, today)) return 'Hoy';
    if (sameDay(d, yesterday)) return 'Ayer';

    const opts = { day: 'numeric', month: 'short' };
    if (d.getFullYear() !== today.getFullYear()) opts.year = 'numeric';
    return d.toLocaleDateString('es-AR', opts);
}

function mealCardHTML(m) {
    const img = m.photo_path
        ? `<img src="/${m.photo_path}" alt="meal">`
        : '<div class="meal-icon-placeholder">🍽️</div>';
    const time = m.created_at ? new Date(m.created_at).toLocaleString('es-AR', { hour: '2-digit', minute: '2-digit' }) : '';

    return `
<div class="meal-card">
    <button class="meal-delete-btn" onclick="deleteMeal(${m.id})" title="Eliminar comida">🗑️</button>
    ${img}
    <div class="meal-info">
        <div style="display:flex;justify-content:space-between;align-items:start">
            <h4 style="font-size:.95rem;margin-bottom:.2rem">${esc(m.description || 'Comida')}</h4>
            <span style="font-size:.7rem;color:var(--muted);font-weight:600">${time}</span>
        </div>
        <div class="meal-macros">
            <span>🔥 ${Math.round(m.total_calories)} kcal</span>
            <span>🥩 P: ${Math.round(m.total_protein)}g</span>
            <span>🍞 C: ${Math.round(m.total_carbs)}g</span>
            <span>🥑 G: ${Math.round(m.total_fat)}g</span>
        </div>
    </div>
</div>
`;
}

async function deleteMeal(mealId) {
    if (!confirm('¿Estás seguro de que querés eliminar esta comida?')) return;

    try {
        const res = await fetch(`/api/meals/${mealId}`, { method: 'DELETE' });
        const data = await res.json();

        if (data.success) {
            // Success: refresh both views
            loadHistory();
            loadDashboard();
            showAlert('alertGlobal', '✅ Comida eliminada', 'success');
        } else {
            showAlert('alertGlobal', '❌ Error: ' + (data.error || data.message), 'error');
        }
    } catch (err) {
        showAlert('alertGlobal', '❌ Error de conexión: ' + err.message, 'error');
    }
}

/* ═══════════════════════════════════════════════════════════════ */
/*                           CHAT                                 */
/* ═══════════════════════════════════════════════════════════════ */

// ── Thinking Panel helpers ───────────────────────────────────
// STEP_ICONS common constant defined at the top

function resetThinkingPanel() {
    document.getElementById('thinkingSteps').innerHTML = '';
    document.getElementById('thinkingSteps').classList.add('hidden');
    document.getElementById('thLabel').textContent = 'Pensando...';
    const header = document.getElementById('thinkingHeader');
    header.classList.remove('has-steps', 'collapsed');
    const spinner = document.getElementById('thSpinner');
    spinner.className = 'th-spinner';
    spinner.textContent = '';
    document.getElementById('thToggle').style.display = 'none';
}

function addThinkingStep(stepType, label, detail) {
    const steps = document.getElementById('thinkingSteps');
    steps.classList.remove('hidden');
    document.getElementById('thinkingHeader').classList.add('has-steps');
    document.getElementById('thToggle').style.display = '';

    const icon = STEP_ICONS[stepType] || '💬';
    const step = document.createElement('div');
    step.className = `thinking-step type-${stepType}`;
    step.innerHTML = `
        <span class="step-icon">${icon}</span>
        <div class="step-body">
            <div class="step-label">${esc(label)}</div>
            ${detail ? `<div class="step-detail">${esc(String(detail).substring(0, 80))}</div>` : ''}
        </div>`;
    steps.appendChild(step);
    steps.scrollTop = steps.scrollHeight;

    document.getElementById('thLabel').textContent = label;
    scrollChat();
}

function markThinkingDone() {
    const spinner = document.getElementById('thSpinner');
    spinner.className = 'th-check';
    spinner.textContent = '✓';
    document.getElementById('thLabel').textContent = 'Razonamiento completado';
    setTimeout(() => {
        document.getElementById('thinkingHeader').classList.add('collapsed');
        document.getElementById('thinkingSteps').classList.add('hidden');
    }, 800);
}

function toggleThinking() {
    const header = document.getElementById('thinkingHeader');
    const steps = document.getElementById('thinkingSteps');
    header.classList.toggle('collapsed');
    steps.classList.toggle('hidden');
}

async function sendChat() {
    if (!currentProfileId) { showAlert('alertGlobal', '⚠️ Seleccioná un perfil primero', 'error'); return; }
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    const now = new Date().toISOString();
    appendChat('user', msg, now);

    const typing = document.getElementById('chatTyping');
    resetThinkingPanel();
    typing.style.display = 'flex';
    scrollChat();

    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile_id: currentProfileId, message: msg }),
        });

        if (!response.ok) throw new Error('Error en la respuesta del servidor');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.type === 'step') {
                            addThinkingStep(data.step_type || 'thinking', data.label || data.text || '', data.detail || '');
                        } else if (data.type === 'progress') {
                            addThinkingStep('thinking', data.text || '', '');
                        } else if (data.type === 'final') {
                            markThinkingDone();
                            setTimeout(() => {
                                typing.style.display = 'none';
                                appendChat('assistant', data.text, new Date().toISOString());
                            }, 900);
                        } else if (data.type === 'error') {
                            typing.style.display = 'none';
                            appendChat('assistant', '❌ Error: ' + data.text, new Date().toISOString());
                        }
                    } catch (e) {
                        console.error('Error parseando SSE:', e, line);
                    }
                }
            }
        }
    } catch (err) {
        typing.style.display = 'none';
        appendChat('assistant', '❌ Error de conexión: ' + err.message, new Date().toISOString());
    } finally {
        // Refresh model status in case a fallback happened (both chat and vision)
        fetchModels('chat');
        fetchModels('vision');
    }
}

// Track last rendered date to know when to insert a separator
let _lastChatDate = '';

function formatDateLabel(isoStr) {
    const d = new Date(isoStr);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

    if (sameDay(d, today)) return 'Hoy';
    if (sameDay(d, yesterday)) return 'Ayer';

    return d.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' });
}

function formatTime(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function appendChat(role, content, isoTimestamp) {
    const container = document.getElementById('chatMessages');
    const typing = document.getElementById('chatTyping');

    // Insert date separator if date changed
    if (isoTimestamp) {
        const dateLabel = formatDateLabel(isoTimestamp);
        if (dateLabel !== _lastChatDate) {
            _lastChatDate = dateLabel;
            const sep = document.createElement('div');
            sep.className = 'chat-date-separator';
            sep.textContent = dateLabel;
            container.insertBefore(sep, typing);
        }
    }

    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;

    // Simple markdown-like rendering for assistant
    let html = '';
    if (role === 'assistant') {
        html = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    } else {
        html = esc(content);
    }

    // Add timestamp
    const timeStr = isoTimestamp ? formatTime(isoTimestamp) : '';
    if (timeStr) {
        html += `<span class="msg-time">${timeStr}</span>`;
    }

    div.innerHTML = html;
    container.insertBefore(div, typing);
    scrollChat();
}

function scrollChat() {
    const c = document.getElementById('chatMessages');
    c.scrollTop = c.scrollHeight;
}

async function loadChatHistory() {
    if (!currentProfileId) return;
    const res = await fetch(`/api/chat/${currentProfileId}`);
    const data = await res.json();

    const container = document.getElementById('chatMessages');
    const typing = document.getElementById('chatTyping');
    container.innerHTML = '';
    container.appendChild(typing);
    _lastChatDate = '';

    if (data.success && data.data.length) {
        data.data.forEach(m => appendChat(m.role, m.content, m.created_at));
    } else {
        const welcome = document.createElement('div');
        welcome.className = 'chat-msg assistant';
        welcome.innerHTML = '<p>👋 ¡Hola! Soy tu agente de salud nutricional. Preguntame lo que quieras.</p>';
        container.insertBefore(welcome, typing);
    }
    scrollChat();
}

async function clearChat() {
    if (!currentProfileId) return;
    await fetch(`/api/chat/${currentProfileId}`, { method: 'DELETE' });
    const container = document.getElementById('chatMessages');
    const typing = document.getElementById('chatTyping');
    container.innerHTML = '';
    container.appendChild(typing);
    _lastChatDate = '';
    const welcome = document.createElement('div');
    welcome.className = 'chat-msg assistant';
    welcome.innerHTML = '<p>👋 Chat limpiado. ¿En qué puedo ayudarte?</p>';
    container.insertBefore(welcome, typing);
}

function toggleExamples() {
    document.getElementById('chatExamples').classList.toggle('hidden');
}

function useExample(btn) {
    let text = btn.dataset.query;
    if (!text) {
        text = btn.textContent.replace(/^[\s\p{Emoji_Presentation}\p{Extended_Pictographic}]+/u, '').trim();
    }
    document.getElementById('chatInput').value = text;
    document.getElementById('chatExamples').classList.add('hidden');
    document.getElementById('chatInput').focus();
}

/* ═══════════════════════════════════════════════════════════════ */
/*                         UTILITIES                              */
/* ═══════════════════════════════════════════════════════════════ */
function showAlert(containerId, msg, type) {
    const el = document.getElementById(containerId);
    el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
    setTimeout(() => { el.innerHTML = ''; }, 6000);
}

function esc(s) {
    if (!s) return '';
    const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return s.replace(/[&<>"']/g, c => m[c]);
}

/* ═══════════════════════════════════════════════════════════════ */
/*                        MODELS MANAGER                          */
/* ═══════════════════════════════════════════════════════════════ */
async function fetchModels(category = 'chat') {
    try {
        const res = await fetch(`/api/models?category=${category}`);
        const data = await res.json();
        if (data.success) {
            const selectorId = category === 'chat' ? 'modelSelector' : 'visionModelSelector';
            const indicatorId = category === 'chat' ? 'modelStatusIndicator' : 'visionModelStatusIndicator';
            
            const selector = document.getElementById(selectorId);
            const indicator = document.getElementById(indicatorId);
            
            if (!selector || !indicator) return;

            // Clear current options
            selector.innerHTML = '';
            
            let activeModel = null;
            
            data.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = m.name + (!m.available ? ' (❌ Agotado)' : '');
                opt.disabled = !m.available;
                if (m.active) {
                    opt.selected = true;
                    activeModel = m;
                }
                selector.appendChild(opt);
            });
            
            if (activeModel) {
                if (activeModel.available) {
                    indicator.textContent = `✅ Usando ${activeModel.name}`;
                    indicator.style.color = '#fff';
                } else {
                    indicator.textContent = `⚠️ ${activeModel.name} agotado`;
                    indicator.style.color = '#ffccd5';
                }
            }
        }
    } catch (e) {
        console.error(`Error fetching models for ${category}:`, e);
    }
}

async function changeModel(category = 'chat') {
    const selectorId = category === 'chat' ? 'modelSelector' : 'visionModelSelector';
    const model_id = document.getElementById(selectorId).value;
    try {
        const res = await fetch('/api/models/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, model_id })
        });
        const data = await res.json();
        if (data.success) {
            fetchModels(category); // Refresh labels
        } else {
            alert('Error al cambiar modelo: ' + data.error);
        }
    } catch (e) {
        console.error(`Error selecting model for ${category}:`, e);
    }
}
