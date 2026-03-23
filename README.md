# 🧬 NutriAgent — Health & Nutrition Manager

**NutriAgent** es un Agente de Intervención Metabólica de Precisión Multimodal construido con Flask y **LangChain**. 

No es un simple contador de calorías, sino un agente impulsado por inteligencia artificial que combina **Visión por Computadora**, **Llamadas a Herramientas (Tool Calling)** y **Retrieval-Augmented Generation (RAG)** para actuar como un asistente nutricional en tiempo real basado en las Guías Alimentarias para la Población Argentina (GAPA).

## 🚀 Características y Arquitectura

### 🧠 Inteligencia Artificial y LangChain
- 🔗 **LangChain Adapter** - Interfaz agnóstica de modelos que permite conectar fácilmente OpenAI, Anthropic, Gemini, etc.
- 👁️ **Visión Multimodal** - Identifica alimentos y estima porciones a partir de fotos (sin alucinaciones calóricas).
- 🛠️ **Tool Calling** - Búsqueda automática de nutrientes vía la API de **Open Food Facts**.
- 🔍 **RAG System (ChromaDB)** - Generación de respuestas nutricionales fundamentadas utilizando Embeddings de *Sentence-Transformers* y una base vectorial con el manual de intervenciones de las GAPA.

### ⚙️ Arquitectura de Software
- 🏗️ **Arquitectura Hexagonal** - Separación estricta entre Adaptadores (LangChain, SQLite, Chroma) y Dominio.
- 🔌 **Dependency Injection** - Inyección total de dependencias vía un contenedor centralizado.
- 💾 **Persistencia Híbrida** - SQLite (Perfiles, Comidas, Chat) + Vector DB (Contexto nutricional).
- 🔄 **API REST Completa** - Rutas y controladores segregados para RAG y Perfilamiento Dietario.

## 📦 Requisitos Previos

- Python 3.7 o superior
- pip (gestor de paquetes de Python)

## 🔧 Instalación

1. **Clonar o descargar el proyecto**
   Puedes descargar el proyecto desde el repositorio oficial: [https://github.com/lucianogiammarini/nutri-agent](https://github.com/lucianogiammarini/nutri-agent), o alternativamente descargar el archivo `.zip` adjunto.
   ```bash
   cd nutri-agent
   ```

2. **Crear un entorno virtual (recomendado)**
   ```bash
   python -m venv venv
   ```

3. **Activar el entorno virtual**
   
   En macOS/Linux:
   ```bash
   source venv/bin/activate
   ```
   
   En Windows:
   ```bash
   venv\Scripts\activate
   ```

4. **Configurar Variables de Entorno (.env)**
   Debes crear un archivo `.env` en la raíz del proyecto. Puedes copiar el ejemplo provisto:
   ```bash
   cp .env.example .env
   ```
   Luego abre el archivo `.env` y completa las variables:
   - **OPENAI_API_KEY**: Ingresa a la [Plataforma OpenAI](https://platform.openai.com/) y crea tu API Key secreta. Es obligatoria para que el Agente RAG y el modelo de Visión (gpt-4o) puedan funcionar.
   - **USDA_API_KEY**: (Opcional) Crea tu llave gratuita en [USDA FoodData Central](https://fdc.nal.usda.gov/api-key-signup.html). Por defecto el sistema usará `DEMO_KEY`, la cual funciona perfecto para pruebas locales pero tiene un límite de 30 consultas por hora.

5. **Instalar las dependencias**
   ```bash
   pip install -r requirements.txt
   ```

## ▶️ Uso

1. **Ejecutar la aplicación**
   ```bash
   python app.py
   ```

2. **Acceder a la aplicación**
   
   **Desde tu computador:**
   ```
   http://127.0.0.1:5000/
   ```
   o
   ```
   http://localhost:5000/
   ```

3. **Acceder desde otros dispositivos en la misma red (móvil, tablet, etc.)**
   
   La aplicación está configurada con `host='0.0.0.0'`, lo que permite el acceso desde cualquier dispositivo en tu red local.
   
   **Pasos:**
   
   a. **Obtén la IP de tu computador:**
   
   En macOS/Linux:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
   
   En Windows:
   ```bash
   ipconfig
   ```
   
   Busca tu dirección IP local (generalmente algo como `192.168.x.x` o `10.0.x.x`)
   
   b. **Desde tu celular o tablet (conectado a la misma red WiFi):**
   
   Abre el navegador y visita:
   ```
   http://TU_IP_LOCAL:5000/
   ```
   
   Ejemplo: `http://192.168.1.10:5000/`

   > ⚠️ **Nota de Seguridad:** Asegúrate de que tu firewall permita conexiones en el puerto 5000. Esta configuración solo debe usarse en redes de confianza (tu red doméstica).

## 📁 Estructura del Proyecto

```
curso5/
│
├── app.py              # Archivo principal de la aplicación Flask
├── requirements.txt    # Dependencias del proyecto
├── README.md          # Este archivo
│
├── static/            # Archivos estáticos (CSS, JS, imágenes)
│
└── templates/         # Plantillas HTML (Jinja2)
```

## 📚 Tecnologías Utilizadas

### Core Backend & Arquitectura
- **Flask 3.1.3** - Framework web y API REST
- **Arquitectura Hexagonal & DI** - Puertos, Adaptadores y Contenedor de Dependencias
- **SQLite3** - Almacenamiento relacional
- **Jinja2** - Motor de UI

### AI & LangChain Ecosystem
- **LangChain Core & OpenAI** - Orquestación del Agente, Modelos (ej: gpt-4o, gpt-4o-mini) y Tool bindings.
- **ChromaDB** - Base de datos vectorial local para el Knowledge Base del RAG.
- **Sentence-Transformers** - Modelos de embeddings locales para el motor de búsqueda semántica.
- **Pillow & Base64** - Procesamiento, compresión y codificación de imágenes para el pipeline visual.

### APIs de Terceros
- **FoodData Central API** - Recuperación asíncrona y precisa de perfiles de macronutrientes.
