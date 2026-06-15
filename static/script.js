/* ============================================================
   NayePankh AI Smart Assistant Platform — Main JavaScript
   Version: 2.0.0
   Author: NayePankh Foundation

   Complete client-side functionality including:
   • Dark/Light mode toggle with localStorage persistence
   • Real-time chat with typing indicator
   • Voice input via Web Speech API
   • Dashboard analytics with Chart.js
   • FAQ management (CRUD)
   • Toast notifications
   • Registration form validation
   • Responsive sidebar toggle
   ============================================================ */

'use strict';

/* ──────────────────────────────────────────────────────────────
   1. DARK MODE TOGGLE
   ────────────────────────────────────────────────────────────── */

/**
 * Initialise dark mode from saved preference or system default.
 * Applies the theme on first paint to avoid flash of wrong theme.
 */
function initDarkMode() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else {
    // Respect system preference if nothing saved
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (prefersDark) {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  }
  updateToggleUI();

  // Bind every toggle button on the page
  document.querySelectorAll('.dark-mode-toggle').forEach((btn) => {
    btn.addEventListener('click', toggleDarkMode);
  });
}

/**
 * Toggle between light and dark themes and persist choice.
 */
function toggleDarkMode() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateToggleUI();
}

/**
 * Sync toggle switch visuals and icon to the active theme.
 */
function updateToggleUI() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

  document.querySelectorAll('.toggle-switch').forEach((sw) => {
    sw.classList.toggle('active', isDark);
  });

  document.querySelectorAll('.toggle-icon').forEach((icon) => {
    icon.textContent = isDark ? '🌙' : '☀️';
  });
}


/* ──────────────────────────────────────────────────────────────
   2. CHAT FUNCTIONALITY
   ────────────────────────────────────────────────────────────── */

/**
 * Bootstrap chat-related event listeners (only if the chat UI exists).
 */
function initChat() {
  const chatInput = document.getElementById('chat-input');
  const sendBtn   = document.getElementById('send-btn');
  if (!chatInput) return; // not on a chat page

  // Guard: if the inline IIFE in index.html already bound chat handlers, skip
  if (window.__chatInitialised) return;
  window.__chatInitialised = true;

  // Send on button click
  if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
  }

  // Send on Enter key (Shift+Enter for new line in future)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Quick-action buttons inject text and auto-send
  document.querySelectorAll('.quick-action-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const text = btn.getAttribute('data-message') || btn.textContent.trim();
      chatInput.value = text;
      sendMessage();
    });
  });
}

/**
 * Send the user's message to the backend and display the response.
 */
async function sendMessage() {
  const chatInput = document.getElementById('chat-input');
  const langSelect = document.getElementById('language-selector');
  const message = chatInput.value.trim();

  if (!message) return;

  const language = langSelect ? langSelect.value : 'en';

  // 1 — Show user bubble immediately
  displayMessage('user', message);
  chatInput.value = '';
  chatInput.focus();

  // 2 — Show typing indicator
  showTypingIndicator();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, language }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }

    const data = await response.json();
    hideTypingIndicator();

    // 3 — Display bot response (HTML for receipts, plain text otherwise)
    const isHTML = Boolean(data.is_receipt);
    displayMessage('bot', data.response, isHTML);
  } catch (error) {
    hideTypingIndicator();
    displayMessage('bot', 'Sorry, something went wrong. Please try again.');
    showNotification('Failed to send message. Check your connection.', 'error');
    console.error('Chat error:', error);
  }
}

/**
 * Render a chat message bubble into the messages container.
 *
 * @param {'user'|'bot'} role   — who sent the message
 * @param {string}        content — message body (text or HTML)
 * @param {boolean}        isHTML  — if true, render as innerHTML
 */
function displayMessage(role, content, isHTML = false) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  // Outer wrapper
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${role}-message`;

  // Avatar
  const avatarDiv = document.createElement('div');
  avatarDiv.className = 'msg-avatar';
  avatarDiv.innerHTML =
    role === 'user'
      ? '<i class="fas fa-user"></i>'
      : '<i class="fas fa-robot"></i>';

  // Content wrapper
  const contentWrapper = document.createElement('div');

  // Bubble
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (isHTML) {
    bubble.innerHTML = content;
  } else {
    bubble.textContent = content;
  }

  // Timestamp
  const timeEl = document.createElement('span');
  timeEl.className = 'message-time';
  timeEl.textContent = formatTime(new Date());

  contentWrapper.appendChild(bubble);
  contentWrapper.appendChild(timeEl);

  messageDiv.appendChild(avatarDiv);
  messageDiv.appendChild(contentWrapper);

  // Insert before the typing indicator if it exists, otherwise append
  const typingEl = container.querySelector('.typing-indicator');
  if (typingEl) {
    container.insertBefore(messageDiv, typingEl);
  } else {
    container.appendChild(messageDiv);
  }

  scrollToBottom();
}

/**
 * Format a Date object to HH:MM (24-hour).
 */
function formatTime(date) {
  const h = String(date.getHours()).padStart(2, '0');
  const m = String(date.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

/**
 * Show the animated typing indicator.
 */
function showTypingIndicator() {
  const indicator = document.querySelector('.typing-indicator');
  if (indicator) {
    indicator.classList.add('active');
    scrollToBottom();
  }
}

/**
 * Hide the typing indicator.
 */
function hideTypingIndicator() {
  const indicator = document.querySelector('.typing-indicator');
  if (indicator) {
    indicator.classList.remove('active');
  }
}

/**
 * Scroll the chat container to the very bottom.
 */
function scrollToBottom() {
  const container = document.getElementById('chat-messages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}


/* ──────────────────────────────────────────────────────────────
   3. VOICE INPUT (Web Speech API) — FIXED: continuous + interim
   ────────────────────────────────────────────────────────────── */

let recognition  = null;
let isRecording  = false;
let finalTranscript   = '';  // Confirmed words
let interimTranscript = '';  // Words being processed

/**
 * Initialise voice input with CONTINUOUS mode and INTERIM results.
 *
 * KEY FIXES over the original implementation:
 *   1. continuous = true        → keeps listening until user clicks stop
 *   2. interimResults = true    → shows live text as user speaks
 *   3. Iterates ALL results     → builds the complete sentence in continuous mode
 *   4. Auto-restarts on silence → browser fires 'end' during pauses; we restart
 *   5. Manual stop-to-send      → message is sent only when user clicks mic again
 */
function initVoice() {
  const voiceBtn = document.getElementById('voice-btn');
  if (!voiceBtn) return;

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    // Browser doesn't support speech recognition — hide the button
    voiceBtn.classList.add('hidden');
    console.warn('Speech Recognition API not supported in this browser.');
    return;
  }

  recognition = new SpeechRecognition();

  // ── KEY FIX 1: continuous = true ──
  // Without this, the browser stops after the first detected pause,
  // which cuts sentences short (e.g. "My name" instead of "My name is Ajai").
  recognition.continuous = true;

  // ── KEY FIX 2: interimResults = true ──
  // Shows real-time transcription in the input field so the user
  // can see what's being captured while speaking.
  recognition.interimResults = true;

  recognition.maxAlternatives = 1;

  // Match the currently selected language when possible
  const langMap = {
    en: 'en-US',
    hi: 'hi-IN',
    ta: 'ta-IN',
    te: 'te-IN',
    kn: 'kn-IN',
  };

  voiceBtn.addEventListener('click', () => {
    const chatInput = document.getElementById('chat-input');

    if (isRecording) {
      // ── STOP recording and send ──
      isRecording = false;
      voiceBtn.classList.remove('recording');
      recognition.stop();

      // Send the accumulated transcript
      const fullText = (finalTranscript + interimTranscript).trim();
      if (fullText && chatInput) {
        chatInput.value = fullText;
        chatInput.placeholder = 'Type your message...';
        // Call the global sendMessage exposed by index.html's inline IIFE
        if (typeof window.sendMessage === 'function') {
          window.sendMessage(fullText);
        }
      }
      // Reset
      finalTranscript = '';
      interimTranscript = '';
      return;
    }

    // ── START recording ──
    finalTranscript = '';
    interimTranscript = '';
    if (chatInput) {
      chatInput.value = '';
      chatInput.placeholder = '🎤 Listening... Click mic again to stop & send';
    }

    // Set recognition language
    const langSelect = document.getElementById('language-selector');
    const langCode = langSelect ? langSelect.value : 'en';
    recognition.lang = langMap[langCode] || 'en-US';

    try {
      recognition.start();
      isRecording = true;
      voiceBtn.classList.add('recording');
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
      showNotification('Could not start voice input. Please try again.', 'error');
    }
  });

  // ── KEY FIX 3: iterate ALL results ──
  // In continuous mode, event.results accumulates. We must loop through
  // every result to build the complete sentence, not just results[0].
  recognition.addEventListener('result', (event) => {
    finalTranscript = '';
    interimTranscript = '';

    for (let i = 0; i < event.results.length; i++) {
      const result = event.results[i];
      if (result.isFinal) {
        finalTranscript += result[0].transcript;
      } else {
        interimTranscript += result[0].transcript;
      }
    }

    // Show live transcription in the input field
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.value = finalTranscript + interimTranscript;
    }
  });

  recognition.addEventListener('error', (event) => {
    // 'no-speech' and 'aborted' are expected in continuous mode — not fatal
    if (event.error === 'no-speech' || event.error === 'aborted') {
      return;
    }
    console.error('Speech recognition error:', event.error);
    let msg = 'Voice input error.';
    if (event.error === 'not-allowed') msg = 'Microphone access denied. Please allow it in browser settings.';
    if (event.error === 'network') msg = 'Network error during voice input.';
    showNotification(msg, 'error');
    isRecording = false;
    voiceBtn.classList.remove('recording');
  });

  // ── KEY FIX 4: auto-restart on silence ──
  // The browser fires 'end' when it detects a pause, even in continuous mode.
  // If the user hasn't clicked stop, we restart to keep listening.
  recognition.addEventListener('end', () => {
    if (isRecording) {
      // User hasn't clicked stop — restart to keep capturing
      try {
        recognition.start();
      } catch (e) {
        // Already running or other error — stop gracefully
        isRecording = false;
        voiceBtn.classList.remove('recording');
        const chatInput = document.getElementById('chat-input');
        if (chatInput) chatInput.placeholder = 'Type your message...';
      }
      return;
    }
    // User clicked stop — clean up
    voiceBtn.classList.remove('recording');
    const chatInput = document.getElementById('chat-input');
    if (chatInput) chatInput.placeholder = 'Type your message...';
  });
}

/* ──────────────────────────────────────────────────────────────
   4. SIDEBAR TOGGLE (Mobile)
   ────────────────────────────────────────────────────────────── */

/**
 * Initialise sidebar open/close for mobile viewports.
 */
function initSidebar() {
  const hamburger = document.querySelector('.hamburger-btn');
  const sidebar   = document.querySelector('.sidebar');
  const overlay   = document.querySelector('.sidebar-overlay');
  if (!hamburger || !sidebar) return;

  hamburger.addEventListener('click', () => {
    sidebar.classList.toggle('active');
    if (overlay) overlay.classList.toggle('active');
  });

  // Close sidebar when clicking the overlay
  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('active');
      overlay.classList.remove('active');
    });
  }

  // Close sidebar when window resizes above mobile breakpoint
  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
      sidebar.classList.remove('active');
      if (overlay) overlay.classList.remove('active');
    }
  });
}


/* ──────────────────────────────────────────────────────────────
   5. DASHBOARD CHARTS (Chart.js)
   ────────────────────────────────────────────────────────────── */

/**
 * Fetch analytics data and render Chart.js charts on the dashboard.
 * Only runs if the expected canvas elements exist on the page.
 */
async function initDashboard() {
  const volunteersCanvas = document.getElementById('volunteers-chart');
  const donationsCanvas  = document.getElementById('donations-chart');
  const chatUsageCanvas  = document.getElementById('chat-usage-chart');

  // Bail out if no chart canvases — we're not on the dashboard
  if (!volunteersCanvas && !donationsCanvas && !chatUsageCanvas) return;

  // NGO brand colour palette
  const colors = {
    primary:   '#e94560',
    secondary: '#0f3460',
    orange:    '#f97316',
    blue:      '#3b82f6',
    green:     '#10b981',
    purple:    '#8b5cf6',
  };

  // Default / fallback data in case the API is unavailable
  let analyticsData = {
    volunteers: {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      data:   [12, 19, 28, 35, 42, 55],
    },
    donations: {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      data:   [5000, 8000, 6500, 12000, 9500, 15000],
    },
    chatUsage: {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      data:   [45, 62, 78, 55, 90, 40, 35],
    },
  };

  // Attempt to load live data
  try {
    const res = await fetch('/api/analytics');
    if (res.ok) {
      const live = await res.json();
      analyticsData = { ...analyticsData, ...live };
    }
  } catch (err) {
    console.warn('Could not load analytics, using defaults:', err);
  }

  // ── Volunteers Line Chart ──
  if (volunteersCanvas) {
    const ctx = volunteersCanvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.25)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.02)');

    new Chart(ctx, {
      type: 'line',
      data: {
        labels: analyticsData.volunteers.labels,
        datasets: [{
          label: 'Volunteers',
          data: analyticsData.volunteers.data,
          borderColor: colors.blue,
          backgroundColor: gradient,
          tension: 0.4,
          fill: true,
          pointBackgroundColor: colors.blue,
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: colors.secondary, titleFont: { size: 13 }, bodyFont: { size: 12 } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8' } },
        },
      },
    });
  }

  // ── Donations Bar Chart ──
  if (donationsCanvas) {
    const ctx = donationsCanvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, colors.primary);
    gradient.addColorStop(1, colors.orange);

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: analyticsData.donations.labels,
        datasets: [{
          label: 'Donations (₹)',
          data: analyticsData.donations.data,
          backgroundColor: gradient,
          borderRadius: 8,
          borderSkipped: false,
          barPercentage: 0.6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: colors.secondary,
            callbacks: {
              label: (ctx) => `₹${ctx.parsed.y.toLocaleString('en-IN')}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8', callback: (v) => `₹${v / 1000}k` } },
        },
      },
    });
  }

  // ── Chat Usage Line Chart ──
  if (chatUsageCanvas) {
    const ctx = chatUsageCanvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.25)');
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.02)');

    new Chart(ctx, {
      type: 'line',
      data: {
        labels: analyticsData.chatUsage.labels,
        datasets: [{
          label: 'Messages',
          data: analyticsData.chatUsage.data,
          borderColor: colors.purple,
          backgroundColor: gradient,
          tension: 0.4,
          fill: true,
          pointBackgroundColor: colors.purple,
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: colors.secondary },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8' } },
        },
      },
    });
  }
}


/* ──────────────────────────────────────────────────────────────
   6. FAQ MANAGEMENT (Admin Dashboard)
   ────────────────────────────────────────────────────────────── */

/**
 * Bind FAQ form submission for creating new FAQ entries.
 */
function initFAQForm() {
  const form = document.getElementById('faq-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const question = form.querySelector('[name="question"]');
    const answer   = form.querySelector('[name="answer"]');

    if (!question || !answer) return;

    const qVal = question.value.trim();
    const aVal = answer.value.trim();

    if (!qVal || !aVal) {
      showNotification('Please fill in both fields.', 'error');
      return;
    }

    try {
      const res = await fetch('/api/admin/faq', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: qVal, answer: aVal }),
      });

      if (!res.ok) throw new Error(`Status ${res.status}`);

      showNotification('FAQ added successfully!', 'success');

      // Clear form
      question.value = '';
      answer.value   = '';

      // Reload to reflect the new entry (simple approach)
      setTimeout(() => location.reload(), 800);
    } catch (err) {
      showNotification('Failed to add FAQ. Try again.', 'error');
      console.error('FAQ add error:', err);
    }
  });
}

/**
 * Delete an FAQ entry after user confirmation.
 *
 * @param {number|string} faqId — the ID of the FAQ to delete
 */
async function deleteFAQ(faqId) {
  const confirmed = confirm('Are you sure you want to delete this FAQ?');
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/admin/faq/${faqId}`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error(`Status ${res.status}`);

    showNotification('FAQ deleted.', 'success');

    // Remove table row from the DOM
    const row = document.querySelector(`tr[data-faq-id="${faqId}"]`);
    if (row) {
      row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      row.style.opacity = '0';
      row.style.transform = 'translateX(20px)';
      setTimeout(() => row.remove(), 300);
    }
  } catch (err) {
    showNotification('Failed to delete FAQ.', 'error');
    console.error('FAQ delete error:', err);
  }
}

/**
 * Prompt the admin for an answer and add an unanswered question to the FAQ.
 *
 * @param {string} question — the question text
 */
async function addToFAQ(question) {
  const answer = prompt(`Provide an answer for:\n\n"${question}"`);
  if (!answer || !answer.trim()) return;

  try {
    const res = await fetch('/api/admin/faq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, answer: answer.trim() }),
    });

    if (!res.ok) throw new Error(`Status ${res.status}`);

    showNotification('FAQ answer saved!', 'success');
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    showNotification('Failed to save answer.', 'error');
    console.error('Add-to-FAQ error:', err);
  }
}


/* ──────────────────────────────────────────────────────────────
   7. NOTIFICATION TOASTS
   ────────────────────────────────────────────────────────────── */

/**
 * Show a brief toast notification in the top-right corner.
 *
 * @param {string} message — the notification text
 * @param {'success'|'error'|'info'} type — visual variant
 */
function showNotification(message, type = 'success') {
  // Ensure a container exists
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: 'fas fa-check-circle',
    error:   'fas fa-exclamation-circle',
    info:    'fas fa-info-circle',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<i class="${icons[type] || icons.info}"></i><span>${message}</span>`;

  container.appendChild(toast);

  // Auto-remove after 3.5 seconds
  setTimeout(() => {
    toast.classList.add('removing');
    toast.addEventListener('animationend', () => toast.remove());
  }, 3500);
}


/* ──────────────────────────────────────────────────────────────
   8. REGISTRATION FORM VALIDATION
   ────────────────────────────────────────────────────────────── */

/**
 * Attach client-side validation to the registration form.
 */
function initRegisterForm() {
  const form = document.getElementById('register-form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    // Clear previous errors
    form.querySelectorAll('.field-error').forEach((el) => el.remove());

    let isValid = true;

    const username = form.querySelector('[name="username"]');
    const email    = form.querySelector('[name="email"]');
    const password = form.querySelector('[name="password"]');
    const confirm  = form.querySelector('[name="confirm_password"]');

    // Username: minimum 3 characters
    if (username && username.value.trim().length < 3) {
      showFieldError(username, 'Username must be at least 3 characters.');
      isValid = false;
    }

    // Email: basic format check
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (email && !emailRegex.test(email.value.trim())) {
      showFieldError(email, 'Please enter a valid email address.');
      isValid = false;
    }

    // Password: minimum 6 characters
    if (password && password.value.length < 6) {
      showFieldError(password, 'Password must be at least 6 characters.');
      isValid = false;
    }

    // Confirm password must match
    if (confirm && password && confirm.value !== password.value) {
      showFieldError(confirm, 'Passwords do not match.');
      isValid = false;
    }

    if (!isValid) {
      e.preventDefault();
    }
  });
}

/**
 * Display an inline error message below the given input element.
 *
 * @param {HTMLElement} input — the input to annotate
 * @param {string}      message — the error text
 */
function showFieldError(input, message) {
  const wrapper = input.closest('.input-group') || input.parentElement;
  const errorEl = document.createElement('span');
  errorEl.className = 'field-error';
  errorEl.textContent = message;
  wrapper.appendChild(errorEl);

  // Highlight the input
  input.style.borderColor = '#ef4444';
  input.addEventListener(
    'focus',
    () => {
      input.style.borderColor = '';
      const existing = wrapper.querySelector('.field-error');
      if (existing) existing.remove();
    },
    { once: true }
  );
}


/* ──────────────────────────────────────────────────────────────
   9. PAGE LOAD — INITIALISATION ORCHESTRATOR
   ────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  // Theme must be first to avoid flash of unstyled content
  initDarkMode();

  // Chat (only on chat pages)
  initChat();

  // Voice input (only if mic button exists)
  initVoice();

  // Mobile sidebar
  initSidebar();

  // Dashboard charts (only if canvas elements exist)
  initDashboard();

  // FAQ management (only on admin dashboard)
  initFAQForm();

  // Registration validation (only on register page)
  initRegisterForm();

  // Auto-scroll chat to latest message
  if (document.getElementById('chat-messages')) {
    scrollToBottom();
  }

  // Accessibility — reduce motion if user prefers
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.style.setProperty('--transition', 'none');
  }
});
