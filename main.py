from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import sqlite3
import hashlib
import jwt
import datetime
import re
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Transpose Music App")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secret key para JWT
SECRET_KEY = os.getenv("SECRET_KEY", "tu_clave_secreta_super_segura_2024_cambiar_en_produccion")
ALGORITHM = "HS256"

# Inicializar base de datos
def init_db():
    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS songs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  title TEXT,
                  artist TEXT,
                  original_song TEXT NOT NULL,
                  transposed_song TEXT NOT NULL,
                  original_key TEXT,
                  target_key TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

init_db()

# Modelos Pydantic
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TransposeRequest(BaseModel):
    song_text: str
    original_key: str
    target_key: str
    song_title: Optional[str] = None
    artist: Optional[str] = None
    token: Optional[str] = None

class SearchQuery(BaseModel):
    query: str
    token: str

# Funciones auxiliares
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(email: str) -> str:
    payload = {
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload['email']
    except:
        return None

# Sistema de transposición musical
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

def normalize_chord(chord: str) -> str:
    """Normaliza acordes con bemoles a sostenidos"""
    replacements = {
        'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'
    }
    for flat, sharp in replacements.items():
        chord = chord.replace(flat, sharp)
    return chord

def transpose_chord(chord: str, semitones: int) -> str:
    """Transpone un acorde individual"""
    if not chord or chord.strip() == '':
        return chord

    # Normalizar el acorde
    chord = normalize_chord(chord)

    # Extraer la nota raíz (puede ser C, C#, etc.)
    match = re.match(r'^([A-G][#b]?)', chord)
    if not match:
        return chord

    root = match.group(1)
    suffix = chord[len(root):]

    # Normalizar bemoles
    if 'b' in root:
        root = normalize_chord(root)

    if root not in NOTES:
        return chord

    # Calcular nueva posición
    old_index = NOTES.index(root)
    new_index = (old_index + semitones) % 12
    new_root = NOTES[new_index]

    return new_root + suffix

def transpose_song(song_text: str, original_key: str, target_key: str) -> str:
    """Transpone toda la canción"""
    original_key = normalize_chord(original_key)
    target_key = normalize_chord(target_key)

    if original_key not in NOTES or target_key not in NOTES:
        raise ValueError("Tonalidad inválida")

    # Calcular semitonos de diferencia
    semitones = (NOTES.index(target_key) - NOTES.index(original_key)) % 12

    # Patrón para detectar acordes (letras mayúsculas seguidas de modificadores)
    chord_pattern = r'\b([A-G][#b]?(?:m|maj|min|dim|aug|sus|add|[0-9])*)\b'

    def replace_chord(match):
        chord = match.group(1)
        return transpose_chord(chord, semitones)

    transposed = re.sub(chord_pattern, replace_chord, song_text)
    return transposed

# HTML content inline
HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transpose Music App 🎵</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .card {
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.95);
        }
        .search-result:hover {
            background: #f3f4f6;
            cursor: pointer;
        }
    </style>
</head>
<body class="gradient-bg min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="text-center mb-8">
            <h1 class="text-5xl font-bold text-white mb-2">🎵 Transpose Music</h1>
            <p class="text-white text-lg">Transpone tus canciones a cualquier tonalidad</p>
        </div>

        <!-- User Info (hidden by default) -->
        <div id="userInfo" class="hidden mb-4 text-center">
            <span class="text-white text-lg">Hola, <span id="userName" class="font-bold"></span>! 👋</span>
            <button onclick="showLibrary()" class="ml-4 bg-blue-500 text-white px-4 py-1 rounded hover:bg-blue-600">
                📚 Mi Biblioteca
            </button>
            <button onclick="showTransposeForm()" class="ml-2 bg-green-500 text-white px-4 py-1 rounded hover:bg-green-600">
                ➕ Nueva Canción
            </button>
            <button onclick="logout()" class="ml-2 bg-red-500 text-white px-4 py-1 rounded hover:bg-red-600">
                Cerrar Sesión
            </button>
        </div>

        <!-- Auth Section -->
        <div id="authSection" class="max-w-md mx-auto card rounded-lg shadow-2xl p-8 mb-8">
            <div class="flex mb-6 border-b">
                <button id="loginTab" onclick="showLogin()" class="flex-1 py-2 font-semibold border-b-2 border-purple-600">
                    Iniciar Sesión
                </button>
                <button id="registerTab" onclick="showRegister()" class="flex-1 py-2 font-semibold text-gray-500">
                    Registrarse
                </button>
            </div>

            <!-- Login Form -->
            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Email</label>
                    <input type="email" id="loginEmail" required 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                </div>
                <div class="mb-6">
                    <label class="block text-gray-700 mb-2">Contraseña</label>
                    <input type="password" id="loginPassword" required 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                </div>
                <button type="submit" class="w-full bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 font-semibold">
                    Iniciar Sesión
                </button>
            </form>

            <!-- Register Form -->
            <form id="registerForm" class="hidden" onsubmit="handleRegister(event)">
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Nombre</label>
                    <input type="text" id="registerName" required 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Email</label>
                    <input type="email" id="registerEmail" required 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                </div>
                <div class="mb-6">
                    <label class="block text-gray-700 mb-2">Contraseña</label>
                    <input type="password" id="registerPassword" required 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                </div>
                <button type="submit" class="w-full bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 font-semibold">
                    Registrarse
                </button>
            </form>
        </div>

        <!-- Library Section -->
        <div id="librarySection" class="hidden max-w-6xl mx-auto">
            <div class="card rounded-lg shadow-2xl p-8 mb-6">
                <h2 class="text-3xl font-bold mb-6 text-gray-800">📚 Mi Biblioteca de Canciones</h2>

                <!-- Search Bar -->
                <div class="mb-6">
                    <div class="relative">
                        <input type="text" id="searchInput" placeholder="🔍 Buscar por título o artista..." 
                               oninput="handleSearch()"
                               class="w-full px-4 py-3 border-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600 text-lg">
                        <div id="searchResults" class="absolute w-full bg-white border rounded-lg shadow-lg mt-1 hidden z-10 max-h-96 overflow-y-auto">
                        </div>
                    </div>
                </div>

                <!-- Songs List -->
                <div id="songsList" class="space-y-4">
                    <p class="text-gray-500 text-center py-8">Cargando canciones...</p>
                </div>
            </div>
        </div>

        <!-- Transpose Section -->
        <div id="transposeSection" class="hidden max-w-4xl mx-auto">
            <div class="card rounded-lg shadow-2xl p-8 mb-6">
                <h2 class="text-2xl font-bold mb-6 text-gray-800">🎸 Transponer Canción</h2>

                <form onsubmit="handleTranspose(event)">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        <div>
                            <label class="block text-gray-700 mb-2 font-semibold">Título de la Canción</label>
                            <input type="text" id="songTitle" placeholder="Ej: Imagine"
                                   class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                        </div>
                        <div>
                            <label class="block text-gray-700 mb-2 font-semibold">Artista</label>
                            <input type="text" id="songArtist" placeholder="Ej: John Lennon"
                                   class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                        </div>
                    </div>

                    <div class="mb-4">
                        <label class="block text-gray-700 mb-2 font-semibold">Letra y Acordes</label>
                        <textarea id="songText" rows="10" required placeholder="Ejemplo:&#10;C        Am&#10;Esta es mi canción&#10;F         G&#10;En tonalidad de Do"
                                  class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600 font-mono"></textarea>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                        <div>
                            <label class="block text-gray-700 mb-2 font-semibold">Tonalidad Original</label>
                            <select id="originalKey" required class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                                <option value="">Selecciona...</option>
                                <option value="C">C (Do)</option>
                                <option value="C#">C# (Do#)</option>
                                <option value="D">D (Re)</option>
                                <option value="D#">D# (Re#)</option>
                                <option value="E">E (Mi)</option>
                                <option value="F">F (Fa)</option>
                                <option value="F#">F# (Fa#)</option>
                                <option value="G">G (Sol)</option>
                                <option value="G#">G# (Sol#)</option>
                                <option value="A">A (La)</option>
                                <option value="A#">A# (La#)</option>
                                <option value="B">B (Si)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-gray-700 mb-2 font-semibold">Tonalidad Destino</label>
                            <select id="targetKey" required class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-600">
                                <option value="">Selecciona...</option>
                                <option value="C">C (Do)</option>
                                <option value="C#">C# (Do#)</option>
                                <option value="D">D (Re)</option>
                                <option value="D#">D# (Re#)</option>
                                <option value="E">E (Mi)</option>
                                <option value="F">F (Fa)</option>
                                <option value="F#">F# (Fa#)</option>
                                <option value="G">G (Sol)</option>
                                <option value="G#">G# (Sol#)</option>
                                <option value="A">A (La)</option>
                                <option value="A#">A# (La#)</option>
                                <option value="B">B (Si)</option>
                            </select>
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 font-semibold text-lg">
                        🎵 Transponer Canción
                    </button>
                </form>
            </div>

            <!-- Result Section -->
            <div id="resultSection" class="hidden card rounded-lg shadow-2xl p-8">
                <h2 class="text-2xl font-bold mb-4 text-gray-800">✨ Resultado</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <h3 class="font-semibold text-gray-700 mb-2">Original (<span id="resultOriginalKey"></span>)</h3>
                        <pre id="originalText" class="bg-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-sm"></pre>
                    </div>
                    <div>
                        <h3 class="font-semibold text-gray-700 mb-2">Transpuesta (<span id="resultTargetKey"></span>)</h3>
                        <pre id="transposedText" class="bg-green-50 p-4 rounded-lg overflow-auto max-h-96 text-sm"></pre>
                    </div>
                </div>
                <button onclick="copyTransposed()" class="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
                    📋 Copiar Resultado
                </button>
            </div>
        </div>

        <!-- Song Detail Modal -->
        <div id="songModal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div class="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                <div class="p-8">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h2 id="modalTitle" class="text-3xl font-bold text-gray-800"></h2>
                            <p id="modalArtist" class="text-gray-600 text-lg"></p>
                        </div>
                        <button onclick="closeModal()" class="text-gray-500 hover:text-gray-700 text-3xl">×</button>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h3 class="font-semibold text-gray-700 mb-2">Original (<span id="modalOriginalKey"></span>)</h3>
                            <pre id="modalOriginal" class="bg-gray-100 p-4 rounded-lg overflow-auto max-h-96 text-sm"></pre>
                        </div>
                        <div>
                            <h3 class="font-semibold text-gray-700 mb-2">Transpuesta (<span id="modalTargetKey"></span>)</h3>
                            <pre id="modalTransposed" class="bg-green-50 p-4 rounded-lg overflow-auto max-h-96 text-sm"></pre>
                        </div>
                    </div>
                    <div class="mt-6 flex gap-4">
                        <button onclick="copyModalTransposed()" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
                            📋 Copiar
                        </button>
                        <button onclick="deleteCurrentSong()" class="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700">
                            🗑️ Eliminar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentToken = localStorage.getItem('token');
        let currentUser = localStorage.getItem('userName');
        let currentSongId = null;
        let searchTimeout = null;

        if (currentToken && currentUser) {
            showLibrary();
        }

        function showLogin() {
            document.getElementById('loginForm').classList.remove('hidden');
            document.getElementById('registerForm').classList.add('hidden');
            document.getElementById('loginTab').classList.add('border-b-2', 'border-purple-600', 'text-black');
            document.getElementById('loginTab').classList.remove('text-gray-500');
            document.getElementById('registerTab').classList.remove('border-b-2', 'border-purple-600', 'text-black');
            document.getElementById('registerTab').classList.add('text-gray-500');
        }

        function showRegister() {
            document.getElementById('registerForm').classList.remove('hidden');
            document.getElementById('loginForm').classList.add('hidden');
            document.getElementById('registerTab').classList.add('border-b-2', 'border-purple-600', 'text-black');
            document.getElementById('registerTab').classList.remove('text-gray-500');
            document.getElementById('loginTab').classList.remove('border-b-2', 'border-purple-600', 'text-black');
            document.getElementById('loginTab').classList.add('text-gray-500');
        }

        async function handleLogin(event) {
            event.preventDefault();
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (data.success) {
                    currentToken = data.token;
                    currentUser = data.name;
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('userName', data.name);
                    showLibrary();
                    alert('¡Bienvenido! 🎉');
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (error) {
                alert('Error al iniciar sesión: ' + error.message);
            }
        }

        async function handleRegister(event) {
            event.preventDefault();
            const name = document.getElementById('registerName').value;
            const email = document.getElementById('registerEmail').value;
            const password = document.getElementById('registerPassword').value;

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, email, password })
                });

                const data = await response.json();

                if (data.success) {
                    currentToken = data.token;
                    currentUser = data.name;
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('userName', data.name);
                    showLibrary();
                    alert('¡Registro exitoso! 🎉');
                } else {
                    alert('Error: ' + data.message);
                }
            } catch (error) {
                alert('Error al registrarse: ' + error.message);
            }
        }

        function showTransposeForm() {
            document.getElementById('librarySection').classList.add('hidden');
            document.getElementById('transposeSection').classList.remove('hidden');
            document.getElementById('resultSection').classList.add('hidden');
            document.getElementById('songTitle').value = '';
            document.getElementById('songArtist').value = '';
            document.getElementById('songText').value = '';
            document.getElementById('originalKey').value = '';
            document.getElementById('targetKey').value = '';
        }

        async function showLibrary() {
            document.getElementById('authSection').classList.add('hidden');
            document.getElementById('transposeSection').classList.add('hidden');
            document.getElementById('librarySection').classList.remove('hidden');
            document.getElementById('userInfo').classList.remove('hidden');
            document.getElementById('userName').textContent = currentUser;

            await loadSongs();
        }

        async function loadSongs() {
            try {
                const response = await fetch(`/api/my-songs?token=${currentToken}`);
                const data = await response.json();

                const songsList = document.getElementById('songsList');

                if (data.songs.length === 0) {
                    songsList.innerHTML = '<p class="text-gray-500 text-center py-8">No tienes canciones guardadas. ¡Crea tu primera transposición! 🎵</p>';
                } else {
                    songsList.innerHTML = data.songs.map(song => `
                        <div class="border rounded-lg p-4 hover:shadow-lg transition cursor-pointer" onclick="viewSong(${song.id})">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h3 class="text-xl font-bold text-gray-800">${song.title}</h3>
                                    <p class="text-gray-600">${song.artist}</p>
                                    <div class="mt-2 flex gap-4 text-sm text-gray-500">
                                        <span>🎵 ${song.original_key} → ${song.target_key}</span>
                                        <span>📅 ${new Date(song.date).toLocaleDateString()}</span>
                                    </div>
                                </div>
                                <button onclick="event.stopPropagation(); viewSong(${song.id})" 
                                        class="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">
                                    Ver
                                </button>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (error) {
                alert('Error al cargar canciones: ' + error.message);
            }
        }

        function handleSearch() {
            clearTimeout(searchTimeout);
            const query = document.getElementById('searchInput').value.trim();

            if (query.length < 2) {
                document.getElementById('searchResults').classList.add('hidden');
                return;
            }

            searchTimeout = setTimeout(async () => {
                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query, token: currentToken })
                    });

                    const data = await response.json();
                    const resultsDiv = document.getElementById('searchResults');

                    if (data.results.length === 0) {
                        resultsDiv.innerHTML = '<div class="p-4 text-gray-500">No se encontraron resultados</div>';
                    } else {
                        resultsDiv.innerHTML = data.results.map(song => `
                            <div class="p-4 search-result border-b" onclick="viewSong(${song.id})">
                                <div class="font-semibold">${song.title}</div>
                                <div class="text-sm text-gray-600">${song.artist} • ${song.original_key} → ${song.target_key}</div>
                            </div>
                        `).join('');
                    }

                    resultsDiv.classList.remove('hidden');
                } catch (error) {
                    console.error('Error en búsqueda:', error);
                }
            }, 300);
        }

        async function viewSong(songId) {
            document.getElementById('searchResults').classList.add('hidden');
            document.getElementById('searchInput').value = '';

            try {
                const response = await fetch(`/api/song/${songId}?token=${currentToken}`);
                const data = await response.json();

                if (data.success) {
                    currentSongId = songId;
                    document.getElementById('modalTitle').textContent = data.song.title;
                    document.getElementById('modalArtist').textContent = data.song.artist;
                    document.getElementById('modalOriginal').textContent = data.song.original;
                    document.getElementById('modalTransposed').textContent = data.song.transposed;
                    document.getElementById('modalOriginalKey').textContent = data.song.original_key;
                    document.getElementById('modalTargetKey').textContent = data.song.target_key;
                    document.getElementById('songModal').classList.remove('hidden');
                }
            } catch (error) {
                alert('Error al cargar canción: ' + error.message);
            }
        }

        function closeModal() {
            document.getElementById('songModal').classList.add('hidden');
            currentSongId = null;
        }

        function copyModalTransposed() {
            const text = document.getElementById('modalTransposed').textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('¡Copiado al portapapeles! 📋');
            });
        }

        async function deleteCurrentSong() {
            if (!currentSongId) return;

            if (!confirm('¿Estás seguro de eliminar esta canción?')) return;

            try {
                const response = await fetch(`/api/song/${currentSongId}?token=${currentToken}`, {
                    method: 'DELETE'
                });

                const data = await response.json();

                if (data.success) {
                    alert('Canción eliminada ✅');
                    closeModal();
                    loadSongs();
                }
            } catch (error) {
                alert('Error al eliminar: ' + error.message);
            }
        }

        function logout() {
            localStorage.removeItem('token');
            localStorage.removeItem('userName');
            currentToken = null;
            currentUser = null;
            document.getElementById('authSection').classList.remove('hidden');
            document.getElementById('transposeSection').classList.add('hidden');
            document.getElementById('librarySection').classList.add('hidden');
            document.getElementById('userInfo').classList.add('hidden');
            document.getElementById('resultSection').classList.add('hidden');
        }

        async function handleTranspose(event) {
            event.preventDefault();
            const songText = document.getElementById('songText').value;
            const originalKey = document.getElementById('originalKey').value;
            const targetKey = document.getElementById('targetKey').value;
            const songTitle = document.getElementById('songTitle').value || 'Sin título';
            const artist = document.getElementById('songArtist').value || 'Desconocido';

            try {
                const response = await fetch('/api/transpose', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        song_text: songText, 
                        original_key: originalKey, 
                        target_key: targetKey,
                        song_title: songTitle,
                        artist: artist,
                        token: currentToken
                    })
                });

                const data = await response.json();

                if (data.success) {
                    document.getElementById('originalText').textContent = data.original;
                    document.getElementById('transposedText').textContent = data.transposed;
                    document.getElementById('resultOriginalKey').textContent = data.original_key;
                    document.getElementById('resultTargetKey').textContent = data.target_key;
                    document.getElementById('resultSection').classList.remove('hidden');

                    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });

                    alert('¡Canción guardada en tu biblioteca! 📚');
                } else {
                    alert('Error al transponer: ' + data.message);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        function copyTransposed() {
            const text = document.getElementById('transposedText').textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('¡Copiado al portapapeles! 📋');
            });
        }

        document.addEventListener('click', function(event) {
            const searchInput = document.getElementById('searchInput');
            const searchResults = document.getElementById('searchResults');
            if (!searchInput.contains(event.target) && !searchResults.contains(event.target)) {
                searchResults.classList.add('hidden');
            }
        });
    </script>
</body>
</html>"""

# Endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CONTENT

@app.post("/api/register")
async def register(user: UserRegister):
    try:
        conn = sqlite3.connect('music_app.db')
        c = conn.cursor()

        hashed_pw = hash_password(user.password)
        c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                  (user.name, user.email, hashed_pw))
        conn.commit()
        conn.close()

        token = create_token(user.email)
        return {"success": True, "message": "Usuario registrado exitosamente", "token": token, "name": user.name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
async def login(user: UserLogin):
    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()

    hashed_pw = hash_password(user.password)
    c.execute("SELECT name FROM users WHERE email = ? AND password = ?",
              (user.email, hashed_pw))
    result = c.fetchone()
    conn.close()

    if result:
        token = create_token(user.email)
        return {"success": True, "message": "Login exitoso", "token": token, "name": result[0]}
    else:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

@app.post("/api/transpose")
async def transpose(request: TransposeRequest):
    try:
        transposed = transpose_song(request.song_text, request.original_key, request.target_key)

        if request.token:
            email = verify_token(request.token)
            if email:
                conn = sqlite3.connect('music_app.db')
                c = conn.cursor()
                c.execute("SELECT id FROM users WHERE email = ?", (email,))
                user = c.fetchone()

                if user:
                    c.execute("""INSERT INTO songs (user_id, title, artist, original_song, transposed_song, 
                                original_key, target_key) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                              (user[0], request.song_title or "Sin título", request.artist or "Desconocido",
                               request.song_text, transposed, request.original_key, request.target_key))
                    conn.commit()
                conn.close()

        return {
            "success": True,
            "original": request.song_text,
            "transposed": transposed,
            "original_key": request.original_key,
            "target_key": request.target_key
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al transponer: {str(e)}")

@app.get("/api/my-songs")
async def get_my_songs(token: str):
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")

    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()
    c.execute("""SELECT s.id, s.title, s.artist, s.original_song, s.transposed_song, s.original_key, 
                 s.target_key, s.created_at 
                 FROM songs s 
                 JOIN users u ON s.user_id = u.id 
                 WHERE u.email = ? 
                 ORDER BY s.created_at DESC""", (email,))
    songs = c.fetchall()
    conn.close()

    return {
        "success": True,
        "songs": [
            {
                "id": s[0],
                "title": s[1],
                "artist": s[2],
                "original": s[3],
                "transposed": s[4],
                "original_key": s[5],
                "target_key": s[6],
                "date": s[7]
            } for s in songs
        ]
    }

@app.post("/api/search")
async def search_songs(search: SearchQuery):
    email = verify_token(search.token)
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")

    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()

    query_pattern = f"%{search.query}%"
    c.execute("""SELECT s.id, s.title, s.artist, s.original_key, s.target_key, s.created_at 
                 FROM songs s 
                 JOIN users u ON s.user_id = u.id 
                 WHERE u.email = ? AND (s.title LIKE ? OR s.artist LIKE ?)
                 ORDER BY s.created_at DESC LIMIT 20""", 
              (email, query_pattern, query_pattern))
    results = c.fetchall()
    conn.close()

    return {
        "success": True,
        "results": [
            {
                "id": r[0],
                "title": r[1],
                "artist": r[2],
                "original_key": r[3],
                "target_key": r[4],
                "date": r[5]
            } for r in results
        ]
    }

@app.get("/api/song/{song_id}")
async def get_song(song_id: int, token: str):
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")

    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()
    c.execute("""SELECT s.id, s.title, s.artist, s.original_song, s.transposed_song, 
                 s.original_key, s.target_key, s.created_at 
                 FROM songs s 
                 JOIN users u ON s.user_id = u.id 
                 WHERE u.email = ? AND s.id = ?""", (email, song_id))
    song = c.fetchone()
    conn.close()

    if not song:
        raise HTTPException(status_code=404, detail="Canción no encontrada")

    return {
        "success": True,
        "song": {
            "id": song[0],
            "title": song[1],
            "artist": song[2],
            "original": song[3],
            "transposed": song[4],
            "original_key": song[5],
            "target_key": song[6],
            "date": song[7]
        }
    }

@app.delete("/api/song/{song_id}")
async def delete_song(song_id: int, token: str):
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")

    conn = sqlite3.connect('music_app.db')
    c = conn.cursor()
    c.execute("""DELETE FROM songs WHERE id = ? AND user_id = (
                 SELECT id FROM users WHERE email = ?)""", (song_id, email))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()

    if deleted:
        return {"success": True, "message": "Canción eliminada"}
    else:
        raise HTTPException(status_code=404, detail="Canción no encontrada")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
