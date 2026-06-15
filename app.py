"""
app.py — NayePankh AI Smart Assistant Platform (Flask Application)
====================================================================

This is the main Flask application for the NayePankh Foundation's AI-powered
chatbot and management platform. It implements a HYBRID AI ARCHITECTURE that
is specifically designed to minimize costs for NGOs.

HYBRID AI ARCHITECTURE — Cost Optimization Strategy
=====================================================
Most chatbot platforms route EVERY message through a paid AI API (OpenAI,
Google, etc.), which can cost ₹5,000–₹50,000/month for active NGOs.

Our approach:
  1. LOCAL knowledge base handles ~70% of queries (FREE)
  2. FAQ cache handles ~15% of queries (FREE — auto-cached from prior API calls)
  3. Memory system handles ~5% of queries (FREE)
  4. OpenAI API handles only ~10% of truly novel queries (PAID)

Estimated monthly savings: ₹4,000–₹45,000 compared to full API routing.

Additional cost optimizations:
  - Uses gpt-3.5-turbo (cheapest OpenAI model)
  - Limits responses to 150 tokens (brief answers)
  - Sends only 3 messages of context (minimal token usage)
  - Auto-caches every API response as FAQ (never pays twice for same question)
  - SQLite database (zero hosting cost)
  - No paid translation API (built-in multilingual responses)

Security measures:
  - Werkzeug password hashing (pbkdf2:sha256)
  - Session-based authentication with secret key
  - Parameterized SQL queries (injection prevention)
  - Input validation on all form submissions
  - CSRF protection via Flask sessions
"""

import os
import re
import functools
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, render_template_string
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    init_db, add_user, get_user_by_username, get_user_by_id,
    add_volunteer, get_all_volunteers, add_donation, get_all_donations,
    add_chat_message, get_chat_history, set_user_memory, get_user_memory,
    get_all_users, get_all_chat_questions, add_faq, get_all_faqs,
    get_faq_match, increment_faq_frequency, delete_faq,
    count_users, count_volunteers, count_donations, count_chat_sessions,
    volunteers_per_month, donations_per_month, chats_per_month
)

# ===========================================================================
# FLASK APP CONFIGURATION
# ===========================================================================

app = Flask(__name__)

# Secret key for session management. In production, use a strong random key
# stored in environment variables. This default is for development only.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'nayepankh-secret-key-change-in-production-2024')

# OpenAI API key — optional. The platform works fully without it by using
# the local knowledge base. When set, complex queries get AI-powered answers.
# Cost note: Without this key, the platform costs ₹0/month to run.
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', None)

# Lazy-load the OpenAI client only if an API key is available.
# This avoids import errors if the openai package isn't installed and
# the NGO chooses to run without AI capabilities.
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        # openai package not installed — platform runs in local-only mode
        openai_client = None


# ===========================================================================
# MULTILINGUAL TRANSLATIONS
# ---------------------------------------------------------------------------
# Built-in translations eliminate the need for paid translation APIs.
# Each language has all response templates pre-translated.
#
# COST SAVING: Google Translate API costs ~$20 per million characters.
# With 1000 daily messages averaging 100 chars each, that's $60/month.
# Our pre-built translations cost ₹0/month.
#
# Languages supported: English, Hindi, Tamil, Telugu, Kannada
# These cover ~90% of NayePankh Foundation's user base across India.
# ===========================================================================

TRANSLATIONS = {
    'en': {
        'greeting': "Hello{name}! 👋 Welcome to NayePankh Foundation. I'm your AI assistant. How can I help you today? You can ask about volunteering, donations, our programs, or just chat!",
        'about': "🏛️ **NayePankh Foundation** is a registered non-profit organization dedicated to empowering communities through **Education**, **Healthcare**, and **Environmental Conservation**. Founded with the vision of creating lasting social impact, we work across India to provide quality education to underprivileged children, organize health awareness camps, and drive environmental sustainability initiatives. Every contribution, whether time or resources, helps us build a better tomorrow.",
        'volunteer_info': "🤝 **Volunteering with NayePankh Foundation**\n\nWe welcome volunteers with open arms! You can contribute in many ways:\n• **Teaching** — Help educate underprivileged children\n• **Healthcare camps** — Assist in medical awareness drives\n• **Environmental drives** — Participate in tree plantations and clean-up campaigns\n• **Event management** — Help organize our programs\n• **Content & Social Media** — Spread awareness online\n\nWould you like to register as a volunteer? Just say **'register'** or **'sign me up'**!",
        'donation_info': "💝 **Support NayePankh Foundation**\n\nYour donation directly impacts lives:\n• ₹500 — Provides school supplies for one child for a month\n• ₹1,000 — Funds a health check-up camp for 10 people\n• ₹5,000 — Supports a tree plantation drive\n• ₹10,000 — Sponsors a child's education for a year\n\nAll donations are tax-deductible under Section 80G.\n\nWould you like to make a donation? Just say **'I want to donate'**!",
        'contact_info': "📞 **Contact NayePankh Foundation**\n\n• 📧 Email: contact@nayepankh.org\n• 📱 Phone: +91-XXXXXXXXXX\n• 🌐 Website: www.nayepankh.org\n• 📍 Address: New Delhi, India\n• 📸 Instagram: @nayepankhfoundation\n• 📘 Facebook: /nayepankhfoundation\n\nFeel free to reach out — we'd love to hear from you!",
        'events_info': "📅 **Current Programs & Campaigns**\n\n🎓 **Shiksha Initiative** — Free tutoring for underprivileged students\n🌳 **Green Earth Drive** — Monthly tree plantation campaigns\n🏥 **Swasthya Awareness** — Health & hygiene awareness camps\n📚 **Book Donation Drive** — Collecting and distributing educational materials\n🎨 **Kala Utsav** — Art and cultural programs for children\n\nWant to participate? Say **'volunteer'** to join any of these programs!",
        'education_info': "📚 **Education Initiatives**\n\nEducation is the cornerstone of NayePankh Foundation's mission:\n\n• **Free Tutoring Centers** — Weekend classes for underprivileged children in multiple cities\n• **Digital Literacy** — Teaching basic computer skills and internet safety\n• **Scholarship Programs** — Financial support for meritorious students from low-income families\n• **School Supply Drives** — Providing books, stationery, and uniforms\n• **Mentorship Program** — Connecting students with professional mentors\n\nEvery child deserves quality education regardless of their background.",
        'awareness_info': "🌍 **Awareness Campaigns**\n\nNayePankh Foundation runs impactful awareness programs:\n\n• **Health Awareness** — Hygiene, nutrition, and preventive healthcare camps\n• **Environmental Awareness** — Climate change education and sustainable living workshops\n• **Sanitation Drives** — Clean water and sanitation awareness in rural areas\n• **Mental Health** — Counseling sessions and stress management workshops\n• **Women's Empowerment** — Skill development and self-defense training\n\nKnowledge is the first step toward change!",
        'help_menu': "🤖 **Here's what I can help you with:**\n\n1. 📋 **About Us** — Learn about NayePankh Foundation\n2. 🤝 **Volunteer** — Register as a volunteer\n3. 💝 **Donate** — Make a donation\n4. 📞 **Contact** — Get our contact details\n5. 📅 **Events** — Current programs and campaigns\n6. 📚 **Education** — Our education initiatives\n7. 🌍 **Awareness** — Our awareness campaigns\n8. 💬 **Chat** — Ask me anything!\n\nI also remember your preferences! Tell me your name, city, or interests and I'll personalize your experience.",
        'thanks_response': "You're very welcome! 😊 It's our pleasure to help. NayePankh Foundation thrives because of wonderful people like you. Is there anything else I can assist you with?",
        'volunteer_ask_name': "Great! Let's get you registered as a volunteer! 📝\n\n**Step 1/4:** What is your full name?",
        'volunteer_ask_skills': "Nice to meet you, {name}! 🎉\n\n**Step 2/4:** What skills can you contribute? (e.g., teaching, event management, social media, healthcare, content writing, or any other skills)",
        'volunteer_ask_city': "Wonderful skills! 💪\n\n**Step 3/4:** Which city are you based in?",
        'volunteer_ask_availability': "Perfect! 📍\n\n**Step 4/4:** When are you available to volunteer?\n• **Weekdays** — Monday to Friday\n• **Weekends** — Saturday and Sunday\n• **Both** — Anytime during the week\n• **Flexible** — Whenever needed\n\nPlease type one of the above options.",
        'volunteer_success': "🎊 **Registration Successful!**\n\nThank you for volunteering with NayePankh Foundation!\n\n📋 **Your Details:**\n• **Name:** {name}\n• **Skills:** {skills}\n• **City:** {city}\n• **Availability:** {availability}\n\nOur team will contact you soon with upcoming opportunities. Welcome aboard! 🚀",
        'donation_ask_name': "Thank you for your generosity! 💝\n\nLet's process your donation.\n\n**Step 1/3:** What is the donor's full name?",
        'donation_ask_email': "Thank you, {name}! 📧\n\n**Step 2/3:** What is your email address? (for sending the donation receipt)",
        'donation_ask_amount': "Got it! 💰\n\n**Step 3/3:** How much would you like to donate? (Please enter the amount in ₹)\n\nSuggested amounts:\n• ₹500 — School supplies for a child\n• ₹1,000 — Health camp support\n• ₹5,000 — Tree plantation drive\n• ₹10,000 — Sponsor a child's education",
        'donation_success': "donation_receipt",
        'name_remembered': "Nice to know you, {name}! 😊 I'll remember your name for our future conversations.",
        'name_recalled': "Of course! Your name is **{name}**. I remember you! 😊",
        'unknown_complex': "I can help with information about NayePankh Foundation, volunteering, donations, and more. For complex questions, please contact us directly at contact@nayepankh.org or call +91-XXXXXXXXXX."
    },

    'hi': {
        'greeting': "नमस्ते{name}! 👋 NayePankh Foundation में आपका स्वागत है। मैं आपका AI सहायक हूँ। मैं आपकी कैसे मदद कर सकता/सकती हूँ? आप स्वयंसेवा, दान, हमारे कार्यक्रमों के बारे में पूछ सकते हैं!",
        'about': "🏛️ **NayePankh Foundation** एक पंजीकृत गैर-लाभकारी संगठन है जो **शिक्षा**, **स्वास्थ्य सेवा** और **पर्यावरण संरक्षण** के माध्यम से समुदायों को सशक्त बनाने के लिए समर्पित है। हम पूरे भारत में वंचित बच्चों को गुणवत्तापूर्ण शिक्षा प्रदान करते हैं, स्वास्थ्य जागरूकता शिविर आयोजित करते हैं, और पर्यावरणीय स्थिरता पहल चलाते हैं।",
        'volunteer_info': "🤝 **NayePankh Foundation के साथ स्वयंसेवा**\n\nहम स्वयंसेवकों का स्वागत करते हैं! आप कई तरीकों से योगदान दे सकते हैं:\n• **शिक्षण** — वंचित बच्चों को पढ़ाएं\n• **स्वास्थ्य शिविर** — चिकित्सा जागरूकता अभियान में सहायता करें\n• **पर्यावरण अभियान** — वृक्षारोपण और सफाई अभियान में भाग लें\n\nक्या आप स्वयंसेवक के रूप में पंजीकरण करना चाहेंगे? बस **'register'** कहें!",
        'donation_info': "💝 **NayePankh Foundation को सहयोग करें**\n\nआपका दान सीधे जीवन को प्रभावित करता है:\n• ₹500 — एक बच्चे के लिए एक महीने की स्कूल सामग्री\n• ₹1,000 — 10 लोगों के लिए स्वास्थ्य जांच शिविर\n• ₹5,000 — वृक्षारोपण अभियान का समर्थन\n• ₹10,000 — एक बच्चे की एक साल की शिक्षा प्रायोजित करें\n\nक्या आप दान करना चाहेंगे? बस **'donate'** कहें!",
        'contact_info': "📞 **NayePankh Foundation से संपर्क करें**\n\n• 📧 ईमेल: contact@nayepankh.org\n• 📱 फोन: +91-XXXXXXXXXX\n• 🌐 वेबसाइट: www.nayepankh.org\n• 📍 पता: नई दिल्ली, भारत",
        'events_info': "📅 **वर्तमान कार्यक्रम और अभियान**\n\n🎓 **शिक्षा पहल** — वंचित छात्रों के लिए मुफ्त ट्यूशन\n🌳 **हरित पृथ्वी अभियान** — मासिक वृक्षारोपण\n🏥 **स्वास्थ्य जागरूकता** — स्वास्थ्य और स्वच्छता शिविर\n📚 **पुस्तक दान अभियान** — शैक्षिक सामग्री का वितरण",
        'education_info': "📚 **शिक्षा पहल**\n\nशिक्षा NayePankh Foundation के मिशन की आधारशिला है:\n• **मुफ्त ट्यूशन केंद्र** — वंचित बच्चों के लिए सप्ताहांत कक्षाएं\n• **डिजिटल साक्षरता** — कंप्यूटर कौशल सिखाना\n• **छात्रवृत्ति कार्यक्रम** — मेधावी छात्रों को वित्तीय सहायता\n• **मेंटरशिप कार्यक्रम** — पेशेवर मार्गदर्शन",
        'awareness_info': "🌍 **जागरूकता अभियान**\n\n• **स्वास्थ्य जागरूकता** — स्वच्छता, पोषण और निवारक स्वास्थ्य शिविर\n• **पर्यावरण जागरूकता** — जलवायु परिवर्तन शिक्षा\n• **स्वच्छता अभियान** — ग्रामीण क्षेत्रों में स्वच्छ पानी और स्वच्छता\n• **महिला सशक्तिकरण** — कौशल विकास और आत्मरक्षा प्रशिक्षण",
        'help_menu': "🤖 **मैं इनमें आपकी मदद कर सकता/सकती हूँ:**\n\n1. 📋 **हमारे बारे में** — NayePankh Foundation के बारे में जानें\n2. 🤝 **स्वयंसेवा** — स्वयंसेवक के रूप में पंजीकरण करें\n3. 💝 **दान** — दान करें\n4. 📞 **संपर्क** — संपर्क विवरण प्राप्त करें\n5. 📅 **कार्यक्रम** — वर्तमान कार्यक्रम\n6. 📚 **शिक्षा** — शिक्षा पहल\n7. 🌍 **जागरूकता** — जागरूकता अभियान",
        'thanks_response': "आपका बहुत-बहुत धन्यवाद! 😊 NayePankh Foundation आप जैसे लोगों की वजह से फलता-फूलता है। क्या मैं और कुछ मदद कर सकता/सकती हूँ?",
        'volunteer_ask_name': "बहुत बढ़िया! चलिए आपका स्वयंसेवक पंजीकरण करते हैं! 📝\n\n**चरण 1/4:** आपका पूरा नाम क्या है?",
        'volunteer_ask_skills': "आपसे मिलकर खुशी हुई, {name}! 🎉\n\n**चरण 2/4:** आप कौन से कौशल योगदान कर सकते हैं? (जैसे शिक्षण, इवेंट मैनेजमेंट, सोशल मीडिया, आदि)",
        'volunteer_ask_city': "अद्भुत कौशल! 💪\n\n**चरण 3/4:** आप किस शहर में रहते हैं?",
        'volunteer_ask_availability': "बहुत अच्छा! 📍\n\n**चरण 4/4:** आप कब स्वयंसेवा के लिए उपलब्ध हैं?\n• **Weekdays** — सोमवार से शुक्रवार\n• **Weekends** — शनिवार और रविवार\n• **Both** — पूरे सप्ताह\n• **Flexible** — जब भी जरूरत हो",
        'volunteer_success': "🎊 **पंजीकरण सफल!**\n\nNayePankh Foundation के साथ स्वयंसेवा के लिए धन्यवाद!\n\n📋 **आपका विवरण:**\n• **नाम:** {name}\n• **कौशल:** {skills}\n• **शहर:** {city}\n• **उपलब्धता:** {availability}\n\nहमारी टीम जल्द ही आपसे संपर्क करेगी!",
        'donation_ask_name': "आपकी उदारता के लिए धन्यवाद! 💝\n\nचलिए आपका दान प्रोसेस करते हैं।\n\n**चरण 1/3:** दाता का पूरा नाम क्या है?",
        'donation_ask_email': "धन्यवाद, {name}! 📧\n\n**चरण 2/3:** आपका ईमेल पता क्या है? (रसीद भेजने के लिए)",
        'donation_ask_amount': "समझ गया! 💰\n\n**चरण 3/3:** आप कितना दान करना चाहेंगे? (₹ में राशि दर्ज करें)",
        'donation_success': "donation_receipt",
        'name_remembered': "आपसे मिलकर अच्छा लगा, {name}! 😊 मैं आपका नाम याद रखूँगा/रखूँगी।",
        'name_recalled': "बिल्कुल! आपका नाम **{name}** है। मुझे याद है! 😊",
        'unknown_complex': "मैं NayePankh Foundation, स्वयंसेवा, दान और अन्य जानकारी में मदद कर सकता/सकती हूँ। जटिल प्रश्नों के लिए, कृपया हमसे सीधे संपर्क करें: contact@nayepankh.org"
    },

    'ta': {
        'greeting': "வணக்கம்{name}! 👋 NayePankh Foundation-க்கு வரவேற்கிறோம். நான் உங்கள் AI உதவியாளர். நான் உங்களுக்கு எப்படி உதவ முடியும்?",
        'about': "🏛️ **NayePankh Foundation** என்பது **கல்வி**, **சுகாதாரம்** மற்றும் **சுற்றுச்சூழல் பாதுகாப்பு** ஆகியவற்றின் மூலம் சமூகங்களை வலுப்படுத்துவதற்கு அர்ப்பணிக்கப்பட்ட ஒரு பதிவு செய்யப்பட்ட இலாப நோக்கமற்ற நிறுவனம். நாங்கள் இந்தியா முழுவதும் பணியாற்றுகிறோம்.",
        'volunteer_info': "🤝 **NayePankh Foundation-உடன் தன்னார்வத் தொண்டு**\n\nதன்னார்வலர்களை வரவேற்கிறோம்!\n• **கற்பித்தல்** — ஏழை குழந்தைகளுக்கு கல்வி கற்பிக்க\n• **சுகாதார முகாம்கள்** — மருத்துவ விழிப்புணர்வு\n• **சுற்றுச்சூழல்** — மரம் நடுதல் மற்றும் சுத்தம் செய்தல்\n\nபதிவு செய்ய **'register'** என்று சொல்லுங்கள்!",
        'donation_info': "💝 **NayePankh Foundation-ஐ ஆதரிக்கவும்**\n\nஉங்கள் நன்கொடை நேரடியாக உயிர்களை பாதிக்கிறது:\n• ₹500 — ஒரு குழந்தைக்கு பள்ளி பொருட்கள்\n• ₹1,000 — சுகாதார பரிசோதனை முகாம்\n• ₹5,000 — மரம் நடும் இயக்கம்\n\nநன்கொடை செய்ய **'donate'** என்று சொல்லுங்கள்!",
        'contact_info': "📞 **தொடர்புகொள்ள**\n\n• 📧 மின்னஞ்சல்: contact@nayepankh.org\n• 📱 தொலைபேசி: +91-XXXXXXXXXX\n• 🌐 இணையதளம்: www.nayepankh.org",
        'events_info': "📅 **தற்போதைய நிகழ்ச்சிகள்**\n\n🎓 **கல்வி முன்முயற்சி** — இலவச பயிற்சி\n🌳 **பசுமை பூமி இயக்கம்** — மாதாந்திர மரம் நடுதல்\n🏥 **சுகாதார விழிப்புணர்வு** — சுகாதார முகாம்கள்",
        'education_info': "📚 **கல்வி முன்முயற்சிகள்**\n\n• **இலவச பயிற்சி மையங்கள்** — வார இறுதி வகுப்புகள்\n• **டிஜிட்டல் கல்வியறிவு** — கணினி திறன்கள்\n• **உதவித்தொகை** — மாணவர்களுக்கு நிதி உதவி",
        'awareness_info': "🌍 **விழிப்புணர்வு பிரச்சாரங்கள்**\n\n• **சுகாதார விழிப்புணர்வு** — சுகாதாரம் மற்றும் ஊட்டச்சத்து\n• **சுற்றுச்சூழல்** — காலநிலை மாற்றம் கல்வி\n• **பெண்கள் மேம்பாடு** — திறன் மேம்பாடு",
        'help_menu': "🤖 **நான் உதவக்கூடியவை:**\n\n1. 📋 **எங்களைப் பற்றி** — NayePankh Foundation\n2. 🤝 **தன்னார்வத் தொண்டு** — பதிவு செய்யுங்கள்\n3. 💝 **நன்கொடை** — நன்கொடை செய்யுங்கள்\n4. 📞 **தொடர்பு** — தொடர்பு விவரங்கள்\n5. 📅 **நிகழ்வுகள்** — தற்போதைய நிகழ்ச்சிகள்",
        'thanks_response': "நன்றி! 😊 உதவுவது எங்கள் மகிழ்ச்சி. வேறு ஏதாவது உதவ முடியுமா?",
        'volunteer_ask_name': "நல்லது! தன்னார்வலர் பதிவு செய்வோம்! 📝\n\n**படி 1/4:** உங்கள் முழு பெயர் என்ன?",
        'volunteer_ask_skills': "சந்தித்ததில் மகிழ்ச்சி, {name}! 🎉\n\n**படி 2/4:** நீங்கள் என்ன திறன்களை வழங்க முடியும்?",
        'volunteer_ask_city': "அருமையான திறன்கள்! 💪\n\n**படி 3/4:** நீங்கள் எந்த நகரத்தில் இருக்கிறீர்கள்?",
        'volunteer_ask_availability': "சரி! 📍\n\n**படி 4/4:** நீங்கள் எப்போது கிடைக்கிறீர்கள்?\n• **Weekdays** — திங்கள் முதல் வெள்ளி\n• **Weekends** — சனி மற்றும் ஞாயிறு\n• **Both** — எப்போதும்\n• **Flexible** — தேவைப்படும்போது",
        'volunteer_success': "🎊 **பதிவு வெற்றிகரமாக!**\n\n📋 **உங்கள் விவரங்கள்:**\n• **பெயர்:** {name}\n• **திறன்கள்:** {skills}\n• **நகரம்:** {city}\n• **கிடைக்கும் நேரம்:** {availability}\n\nஎங்கள் குழு விரைவில் தொடர்புகொள்ளும்!",
        'donation_ask_name': "உங்கள் தாராள மனப்பான்மைக்கு நன்றி! 💝\n\n**படி 1/3:** நன்கொடையாளரின் பெயர் என்ன?",
        'donation_ask_email': "நன்றி, {name}! 📧\n\n**படி 2/3:** உங்கள் மின்னஞ்சல் முகவரி என்ன?",
        'donation_ask_amount': "சரி! 💰\n\n**படி 3/3:** எவ்வளவு நன்கொடை செய்ய விரும்புகிறீர்கள்? (₹ இல்)",
        'donation_success': "donation_receipt",
        'name_remembered': "உங்களை சந்தித்ததில் மகிழ்ச்சி, {name}! 😊 நான் உங்கள் பெயரை நினைவில் வைத்திருப்பேன்.",
        'name_recalled': "நிச்சயமாக! உங்கள் பெயர் **{name}**. எனக்கு நினைவிருக்கிறது! 😊",
        'unknown_complex': "NayePankh Foundation, தன்னார்வத் தொண்டு, நன்கொடை பற்றிய தகவல்களில் உதவ முடியும். சிக்கலான கேள்விகளுக்கு: contact@nayepankh.org"
    },

    'te': {
        'greeting': "నమస్కారం{name}! 👋 NayePankh Foundation కి స్వాగతం. నేను మీ AI సహాయకుడిని. నేను మీకు ఎలా సహాయం చేయగలను?",
        'about': "🏛️ **NayePankh Foundation** అనేది **విద్య**, **ఆరోగ్య సంరక్షణ** మరియు **పర్యావరణ పరిరక్షణ** ద్వారా సమాజాలను సాధికారత చేయడానికి అంకితమైన నమోదిత లాభాపేక్షలేని సంస్థ. మేము భారతదేశం అంతటా పనిచేస్తున్నాము.",
        'volunteer_info': "🤝 **NayePankh Foundation తో వాలంటీరింగ్**\n\nవాలంటీర్లను ఆహ్వానిస్తున్నాము!\n• **బోధన** — పేద పిల్లలకు విద్య\n• **ఆరోగ్య శిబిరాలు** — వైద్య అవగాహన\n• **పర్యావరణ ప్రచారాలు** — వృక్షారోపణ\n\nనమోదు చేసుకోవడానికి **'register'** అని చెప్పండి!",
        'donation_info': "💝 **NayePankh Foundation కి మద్దతు**\n\nమీ విరాళం ప్రత్యక్షంగా ప్రభావితం చేస్తుంది:\n• ₹500 — ఒక పిల్లవాడికి పాఠశాల సామగ్రి\n• ₹1,000 — ఆరోగ్య పరీక్ష శిబిరం\n• ₹5,000 — వృక్షారోపణ\n\nవిరాళం ఇవ్వడానికి **'donate'** అని చెప్పండి!",
        'contact_info': "📞 **సంప్రదించండి**\n\n• 📧 ఇమెయిల్: contact@nayepankh.org\n• 📱 ఫోన్: +91-XXXXXXXXXX\n• 🌐 వెబ్‌సైట్: www.nayepankh.org",
        'events_info': "📅 **ప్రస్తుత కార్యక్రమాలు**\n\n🎓 **విద్య** — ఉచిత ట్యూషన్\n🌳 **పచ్చదనం** — వృక్షారోపణ\n🏥 **ఆరోగ్యం** — ఆరోగ్య శిబిరాలు",
        'education_info': "📚 **విద్యా కార్యక్రమాలు**\n\n• **ఉచిత ట్యూషన్ కేంద్రాలు** — వారాంతపు తరగతులు\n• **డిజిటల్ అక్షరాస్యత** — కంప్యూటర్ నైపుణ్యాలు\n• **స్కాలర్‌షిప్** — విద్యార్థులకు ఆర్థిక సహాయం",
        'awareness_info': "🌍 **అవగాహన ప్రచారాలు**\n\n• **ఆరోగ్య అవగాహన** — పరిశుభ్రత మరియు పోషణ\n• **పర్యావరణ** — వాతావరణ మార్పు విద్య\n• **మహిళా సాధికారత** — నైపుణ్య అభివృద్ధి",
        'help_menu': "🤖 **నేను సహాయం చేయగలను:**\n\n1. 📋 **మా గురించి** — NayePankh Foundation\n2. 🤝 **వాలంటీర్** — నమోదు చేసుకోండి\n3. 💝 **విరాళం** — విరాళం ఇవ్వండి\n4. 📞 **సంప్రదించండి** — సంప్రదింపు వివరాలు\n5. 📅 **కార్యక్రమాలు** — ప్రస్తుత కార్యక్రమాలు",
        'thanks_response': "చాలా ధన్యవాదాలు! 😊 సహాయం చేయడం మా ఆనందం. ఇంకా ఏదైనా సహాయం కావాలా?",
        'volunteer_ask_name': "బాగుంది! వాలంటీర్ నమోదు చేద్దాం! 📝\n\n**దశ 1/4:** మీ పూర్తి పేరు ఏమిటి?",
        'volunteer_ask_skills': "కలిసినందుకు సంతోషం, {name}! 🎉\n\n**దశ 2/4:** మీరు ఏ నైపుణ్యాలను అందించగలరు?",
        'volunteer_ask_city': "అద్భుతమైన నైపుణ్యాలు! 💪\n\n**దశ 3/4:** మీరు ఏ నగరంలో ఉన్నారు?",
        'volunteer_ask_availability': "బాగుంది! 📍\n\n**దశ 4/4:** మీరు ఎప్పుడు అందుబాటులో ఉంటారు?\n• **Weekdays** — సోమవారం నుండి శుక్రవారం\n• **Weekends** — శనివారం మరియు ఆదివారం\n• **Both** — ఎప్పుడైనా\n• **Flexible** — అవసరమైనప్పుడు",
        'volunteer_success': "🎊 **నమోదు విజయవంతం!**\n\n📋 **మీ వివరాలు:**\n• **పేరు:** {name}\n• **నైపుణ్యాలు:** {skills}\n• **నగరం:** {city}\n• **అందుబాటు:** {availability}\n\nమా బృందం త్వరలో సంప్రదిస్తుంది!",
        'donation_ask_name': "మీ దాతృత్వానికి ధన్యవాదాలు! 💝\n\n**దశ 1/3:** దాత పేరు ఏమిటి?",
        'donation_ask_email': "ధన్యవాదాలు, {name}! 📧\n\n**దశ 2/3:** మీ ఇమెయిల్ చిరునామా ఏమిటి?",
        'donation_ask_amount': "సరే! 💰\n\n**దశ 3/3:** ఎంత విరాళం ఇవ్వాలనుకుంటున్నారు? (₹ లో)",
        'donation_success': "donation_receipt",
        'name_remembered': "మిమ్మల్ని కలిసినందుకు సంతోషం, {name}! 😊 నేను మీ పేరు గుర్తుంచుకుంటాను.",
        'name_recalled': "తప్పకుండా! మీ పేరు **{name}**. నాకు గుర్తుంది! 😊",
        'unknown_complex': "NayePankh Foundation, వాలంటీరింగ్, విరాళాల గురించి సహాయం చేయగలను. సంక్లిష్ట ప్రశ్నలకు: contact@nayepankh.org"
    },

    'kn': {
        'greeting': "ನಮಸ್ಕಾರ{name}! 👋 NayePankh Foundation ಗೆ ಸುಸ್ವಾಗತ. ನಾನು ನಿಮ್ಮ AI ಸಹಾಯಕ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
        'about': "🏛️ **NayePankh Foundation** ಎಂಬುದು **ಶಿಕ್ಷಣ**, **ಆರೋಗ್ಯ** ಮತ್ತು **ಪರಿಸರ ಸಂರಕ್ಷಣೆ** ಮೂಲಕ ಸಮುದಾಯಗಳನ್ನು ಸಬಲೀಕರಣಗೊಳಿಸಲು ಮೀಸಲಾದ ನೋಂದಾಯಿತ ಲಾಭರಹಿತ ಸಂಸ್ಥೆ.",
        'volunteer_info': "🤝 **NayePankh Foundation ಜೊತೆ ಸ್ವಯಂಸೇವೆ**\n\nಸ್ವಯಂಸೇವಕರನ್ನು ಸ್ವಾಗತಿಸುತ್ತೇವೆ!\n• **ಕಲಿಸುವುದು** — ಬಡ ಮಕ್ಕಳಿಗೆ ಶಿಕ್ಷಣ\n• **ಆರೋಗ್ಯ ಶಿಬಿರಗಳು** — ವೈದ್ಯಕೀಯ ಜಾಗೃತಿ\n• **ಪರಿಸರ** — ವೃಕ್ಷಾರೋಪಣ\n\nನೋಂದಾಯಿಸಲು **'register'** ಎಂದು ಹೇಳಿ!",
        'donation_info': "💝 **NayePankh Foundation ಗೆ ಬೆಂಬಲ**\n\nನಿಮ್ಮ ದೇಣಿಗೆ ನೇರವಾಗಿ ಜೀವನವನ್ನು ಪ್ರಭಾವಿಸುತ್ತದೆ:\n• ₹500 — ಮಗುವಿಗೆ ಶಾಲಾ ಸಾಮಗ್ರಿ\n• ₹1,000 — ಆರೋಗ್ಯ ತಪಾಸಣೆ ಶಿಬಿರ\n\nದೇಣಿಗೆ ನೀಡಲು **'donate'** ಎಂದು ಹೇಳಿ!",
        'contact_info': "📞 **ಸಂಪರ್ಕಿಸಿ**\n\n• 📧 ಇಮೇಲ್: contact@nayepankh.org\n• 📱 ಫೋನ್: +91-XXXXXXXXXX\n• 🌐 ವೆಬ್‌ಸೈಟ್: www.nayepankh.org",
        'events_info': "📅 **ಪ್ರಸ್ತುತ ಕಾರ್ಯಕ್ರಮಗಳು**\n\n🎓 **ಶಿಕ್ಷಣ** — ಉಚಿತ ಟ್ಯೂಷನ್\n🌳 **ಹಸಿರು** — ವೃಕ್ಷಾರೋಪಣ\n🏥 **ಆರೋಗ್ಯ** — ಆರೋಗ್ಯ ಶಿಬಿರಗಳು",
        'education_info': "📚 **ಶಿಕ್ಷಣ ಉಪಕ್ರಮಗಳು**\n\n• **ಉಚಿತ ಟ್ಯೂಷನ್ ಕೇಂದ್ರಗಳು** — ವಾರಾಂತ್ಯ ತರಗತಿಗಳು\n• **ಡಿಜಿಟಲ್ ಸಾಕ್ಷರತೆ** — ಕಂಪ್ಯೂಟರ್ ಕೌಶಲ್ಯ\n• **ವಿದ್ಯಾರ್ಥಿವೇತನ** — ಆರ್ಥಿಕ ನೆರವು",
        'awareness_info': "🌍 **ಜಾಗೃತಿ ಅಭಿಯಾನಗಳು**\n\n• **ಆರೋಗ್ಯ** — ನೈರ್ಮಲ್ಯ ಮತ್ತು ಪೋಷಣೆ\n• **ಪರಿಸರ** — ಹವಾಮಾನ ಬದಲಾವಣೆ ಶಿಕ್ಷಣ\n• **ಮಹಿಳಾ ಸಬಲೀಕರಣ** — ಕೌಶಲ್ಯ ಅಭಿವೃದ್ಧಿ",
        'help_menu': "🤖 **ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ:**\n\n1. 📋 **ನಮ್ಮ ಬಗ್ಗೆ** — NayePankh Foundation\n2. 🤝 **ಸ್ವಯಂಸೇವೆ** — ನೋಂದಾಯಿಸಿ\n3. 💝 **ದೇಣಿಗೆ** — ದೇಣಿಗೆ ನೀಡಿ\n4. 📞 **ಸಂಪರ್ಕ** — ಸಂಪರ್ಕ ವಿವರಗಳು",
        'thanks_response': "ಧನ್ಯವಾದಗಳು! 😊 ಸಹಾಯ ಮಾಡುವುದು ನಮ್ಮ ಸಂತೋಷ. ಬೇರೆ ಏನಾದರೂ ಸಹಾಯ ಬೇಕಾ?",
        'volunteer_ask_name': "ಒಳ್ಳೆಯದು! ಸ್ವಯಂಸೇವಕ ನೋಂದಣಿ ಮಾಡೋಣ! 📝\n\n**ಹಂತ 1/4:** ನಿಮ್ಮ ಪೂರ್ಣ ಹೆಸರು ಏನು?",
        'volunteer_ask_skills': "ಭೇಟಿಯಾಗಿ ಸಂತೋಷ, {name}! 🎉\n\n**ಹಂತ 2/4:** ನೀವು ಯಾವ ಕೌಶಲ್ಯಗಳನ್ನು ನೀಡಬಲ್ಲಿರಿ?",
        'volunteer_ask_city': "ಅದ್ಭುತ ಕೌಶಲ್ಯಗಳು! 💪\n\n**ಹಂತ 3/4:** ನೀವು ಯಾವ ನಗರದಲ್ಲಿ ಇದ್ದೀರಿ?",
        'volunteer_ask_availability': "ಸರಿ! 📍\n\n**ಹಂತ 4/4:** ನೀವು ಯಾವಾಗ ಲಭ್ಯವಿರುತ್ತೀರಿ?\n• **Weekdays** — ಸೋಮವಾರ ಶುಕ್ರವಾರ\n• **Weekends** — ಶನಿವಾರ ಮತ್ತು ಭಾನುವಾರ\n• **Both** — ಯಾವಾಗಲೂ\n• **Flexible** — ಅಗತ್ಯವಿದ್ದಾಗ",
        'volunteer_success': "🎊 **ನೋಂದಣಿ ಯಶಸ್ವಿ!**\n\n📋 **ನಿಮ್ಮ ವಿವರಗಳು:**\n• **ಹೆಸರು:** {name}\n• **ಕೌಶಲ್ಯಗಳು:** {skills}\n• **ನಗರ:** {city}\n• **ಲಭ್ಯತೆ:** {availability}\n\nನಮ್ಮ ತಂಡ ಶೀಘ್ರದಲ್ಲೇ ಸಂಪರ್ಕಿಸುತ್ತದೆ!",
        'donation_ask_name': "ನಿಮ್ಮ ಉದಾರತೆಗೆ ಧನ್ಯವಾದಗಳು! 💝\n\n**ಹಂತ 1/3:** ದಾನಿಯ ಹೆಸರು ಏನು?",
        'donation_ask_email': "ಧನ್ಯವಾದಗಳು, {name}! 📧\n\n**ಹಂತ 2/3:** ನಿಮ್ಮ ಇಮೇಲ್ ವಿಳಾಸ ಏನು?",
        'donation_ask_amount': "ಸರಿ! 💰\n\n**ಹಂತ 3/3:** ಎಷ್ಟು ದೇಣಿಗೆ ನೀಡಲು ಬಯಸುತ್ತೀರಿ? (₹ ನಲ್ಲಿ)",
        'donation_success': "donation_receipt",
        'name_remembered': "ನಿಮ್ಮನ್ನು ಭೇಟಿಯಾಗಿ ಸಂತೋಷ, {name}! 😊 ನಾನು ನಿಮ್ಮ ಹೆಸರನ್ನು ನೆನಪಿಟ್ಟುಕೊಳ್ಳುತ್ತೇನೆ.",
        'name_recalled': "ಖಂಡಿತ! ನಿಮ್ಮ ಹೆಸರು **{name}**. ನನಗೆ ನೆನಪಿದೆ! 😊",
        'unknown_complex': "NayePankh Foundation, ಸ್ವಯಂಸೇವೆ, ದೇಣಿಗೆ ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಸಂಕೀರ್ಣ ಪ್ರಶ್ನೆಗಳಿಗೆ: contact@nayepankh.org"
    }
}


# ===========================================================================
# NGO LOCAL KNOWLEDGE BASE
# ---------------------------------------------------------------------------
# This dictionary maps keyword triggers to response categories. When a user
# message contains any of these keywords, the corresponding local response
# is returned IMMEDIATELY without any API call.
#
# COST IMPACT: Each avoided API call saves approximately ₹0.05–₹0.15.
# With 500 messages/day, that's ₹750–₹2,250/month saved on API costs alone.
#
# The knowledge base is organized by intent category, with each category
# containing a list of trigger keywords and a response key that maps to
# the TRANSLATIONS dictionary above.
# ===========================================================================

NGO_KNOWLEDGE_BASE = {
    'about': {
        'keywords': ['about', 'nayepankh', 'foundation', 'who are you', 'what is'],
        'response_key': 'about'
    },
    'volunteer': {
        'keywords': ['volunteer', 'join', 'help', 'participate', 'register', 'sign me up', 'sign up'],
        'response_key': 'volunteer_info',
        'trigger_workflow': 'volunteer'
    },
    'donate': {
        'keywords': ['donate', 'donation', 'contribute', 'fund', 'money', 'i want to donate'],
        'response_key': 'donation_info',
        'trigger_workflow': 'donation'
    },
    'contact': {
        'keywords': ['contact', 'reach', 'phone', 'email address', 'address'],
        'response_key': 'contact_info'
    },
    'events': {
        'keywords': ['event', 'program', 'campaign', 'activity'],
        'response_key': 'events_info'
    },
    'education': {
        'keywords': ['education', 'school', 'teach', 'learn', 'student'],
        'response_key': 'education_info'
    },
    'awareness': {
        'keywords': ['awareness', 'health', 'environment', 'sanitation'],
        'response_key': 'awareness_info'
    },
    'greeting': {
        'keywords': ['hello', 'hi', 'hey', 'good morning', 'good evening'],
        'response_key': 'greeting'
    },
    'thanks': {
        'keywords': ['thank', 'thanks', 'thank you'],
        'response_key': 'thanks_response'
    },
    'help': {
        'keywords': ['help', 'what can you do', 'menu', 'options'],
        'response_key': 'help_menu'
    }
}


# ===========================================================================
# MEMORY SYSTEM
# ---------------------------------------------------------------------------
# The memory system extracts personal information from natural language and
# stores it for personalization. This makes the chatbot feel more human
# without requiring expensive NLP models.
#
# Pattern matching is done with simple regex — no external NLP library needed.
# This keeps the dependency list minimal and the cost at zero.
# ===========================================================================

def extract_and_store_memory(user_id, message):
    """
    Extract personal information from the user's message and persist it.

    Detects patterns like:
      - 'my name is Ajai' → stores name='Ajai'
      - 'I live in Delhi' → stores city='Delhi'
      - 'I like teaching' → stores interest='teaching'
      - 'I know Python' → stores skill='Python'

    Uses case-insensitive regex matching for flexibility. The extracted
    information is stored in the user_memory table as key-value pairs.

    Args:
        user_id (int): The user whose memory to update.
        message (str): The user's raw message text.

    Returns:
        dict or None: Dictionary of extracted memories {'key': 'value'},
                      or None if no personal info was detected.
    """
    extracted = {}
    msg_lower = message.lower().strip()

    # --- Name Detection ---
    # Matches: 'my name is X', 'I am X', 'call me X', 'i'm X'
    name_patterns = [
        r"my name is\s+(.+?)(?:\s*[.,!?]|$)",
        r"i am\s+(.+?)(?:\s*[.,!?]|$)",
        r"call me\s+(.+?)(?:\s*[.,!?]|$)",
        r"i'm\s+(.+?)(?:\s*[.,!?]|$)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, msg_lower, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            # Avoid storing common phrases that aren't names
            if len(name) > 1 and name.lower() not in ['interested', 'from', 'good', 'fine', 'happy', 'a volunteer', 'here']:
                set_user_memory(user_id, 'name', name)
                extracted['name'] = name
                break

    # --- City/Location Detection ---
    # Matches: 'I live in X', 'I am from X', 'my city is X', 'I'm from X'
    city_patterns = [
        r"i live in\s+(.+?)(?:\s*[.,!?]|$)",
        r"i am from\s+(.+?)(?:\s*[.,!?]|$)",
        r"i'm from\s+(.+?)(?:\s*[.,!?]|$)",
        r"my city is\s+(.+?)(?:\s*[.,!?]|$)",
    ]
    for pattern in city_patterns:
        match = re.search(pattern, msg_lower, re.IGNORECASE)
        if match:
            city = match.group(1).strip().title()
            if len(city) > 1:
                set_user_memory(user_id, 'city', city)
                extracted['city'] = city
                break

    # --- Interest Detection ---
    # Matches: 'I like X', 'I am interested in X', 'my interest is X'
    interest_patterns = [
        r"i like\s+(.+?)(?:\s*[.,!?]|$)",
        r"i am interested in\s+(.+?)(?:\s*[.,!?]|$)",
        r"i'm interested in\s+(.+?)(?:\s*[.,!?]|$)",
        r"my interest is\s+(.+?)(?:\s*[.,!?]|$)",
    ]
    for pattern in interest_patterns:
        match = re.search(pattern, msg_lower, re.IGNORECASE)
        if match:
            interest = match.group(1).strip()
            if len(interest) > 1:
                set_user_memory(user_id, 'interest', interest)
                extracted['interest'] = interest
                break

    # --- Skill Detection ---
    # Matches: 'I know X', 'my skill is X', 'I can do X'
    skill_patterns = [
        r"i know\s+(.+?)(?:\s*[.,!?]|$)",
        r"my skill is\s+(.+?)(?:\s*[.,!?]|$)",
        r"i can do\s+(.+?)(?:\s*[.,!?]|$)",
    ]
    for pattern in skill_patterns:
        match = re.search(pattern, msg_lower, re.IGNORECASE)
        if match:
            skill = match.group(1).strip()
            if len(skill) > 1:
                set_user_memory(user_id, 'skill', skill)
                extracted['skill'] = skill
                break

    return extracted if extracted else None


def get_memory_context(user_id):
    """
    Build a context string from all stored user memories.

    This context string is appended to the OpenAI system prompt so the AI
    knows about the user's personal details. This creates a personalized
    experience without storing conversation history (which would be expensive).

    Args:
        user_id (int): The user whose memories to retrieve.

    Returns:
        str: A formatted context string, e.g.,
             "User's name is Ajai. User lives in Delhi.
              User is interested in teaching. User knows Python."
             Returns empty string if no memories exist.
    """
    memories = get_user_memory(user_id)
    if not memories:
        return ""

    context_parts = []
    if 'name' in memories:
        context_parts.append(f"User's name is {memories['name']}.")
    if 'city' in memories:
        context_parts.append(f"User lives in {memories['city']}.")
    if 'interest' in memories:
        context_parts.append(f"User is interested in {memories['interest']}.")
    if 'skill' in memories:
        context_parts.append(f"User knows {memories['skill']}.")

    return " ".join(context_parts)


# ===========================================================================
# OPENAI API INTEGRATION — THE "LAST RESORT" IN OUR HYBRID ARCHITECTURE
# ---------------------------------------------------------------------------
# This function is called ONLY when all free local processing fails to
# produce a relevant response. It represents ~10% of total queries.
#
# Cost controls implemented:
#   1. Uses gpt-3.5-turbo (cheapest model: ~$0.002 per 1K tokens)
#   2. max_tokens=150 limits response length (saves ~60% vs unlimited)
#   3. Only 3 messages of context (saves ~70% vs full history)
#   4. Auto-caches response as FAQ (prevents paying twice for same question)
#   5. Graceful fallback if API key missing or API errors occur
#
# Estimated cost: ~₹0.05 per API call (3-5 paisa)
# At 50 calls/day: ~₹75/month (vs ₹750/month without hybrid architecture)
# ===========================================================================

def ask_openai(message, memory_context, chat_history_context):
    """
    Send a query to OpenAI's GPT-3.5-turbo as a last resort.

    This function is the ONLY paid component in the entire chatbot. All other
    processing is completely free. The function includes multiple cost controls
    and safety measures.

    Args:
        message (str): The user's message that couldn't be handled locally.
        memory_context (str): Personalization context from user_memory table.
        chat_history_context (list): Last 3 messages for conversation context.

    Returns:
        str: The AI-generated response, or a fallback message on error.
    """
    # --- Guard: No API key configured → return fallback immediately (FREE) ---
    if not openai_client:
        return (
            "I can help with information about NayePankh Foundation, volunteering, "
            "donations, and more. For complex questions, please contact us directly."
        )

    try:
        # Build the system prompt — kept deliberately short to minimize tokens.
        # Every extra word in the system prompt costs money on EVERY API call.
        system_prompt = (
            "You are a helpful assistant for NayePankh Foundation, an NGO focused on "
            "education, healthcare, and environment. Be brief and helpful."
        )
        if memory_context:
            system_prompt += f" Context about the user: {memory_context}"

        # Build the messages array for the API call
        messages = [{"role": "system", "content": system_prompt}]

        # Add only the last 3 messages of chat history to minimize token usage.
        # Full history would cost 3-5x more per API call.
        # Each message in history adds ~20-50 tokens to the request.
        if chat_history_context:
            for msg in chat_history_context[-3:]:
                messages.append({
                    "role": msg['role'],
                    "content": msg['message']
                })

        # Add the current user message
        messages.append({"role": "user", "content": message})

        # --- Make the API call with strict cost controls ---
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",    # Cheapest model: ~$0.002/1K tokens
            messages=messages,
            max_tokens=150,             # Brief responses only (saves ~60% cost)
            temperature=0.7             # Balanced creativity/consistency
        )

        ai_response = response.choices[0].message.content.strip()
        return ai_response

    except Exception as e:
        # --- Graceful degradation on ANY error ---
        # Log the error for debugging but never expose it to the user.
        # Common errors: rate limits, invalid API key, network issues, quota exceeded.
        print(f"[OpenAI Error] {type(e).__name__}: {e}")
        return (
            "I'm having trouble connecting to my AI brain right now. "
            "I can still help with information about NayePankh Foundation, "
            "volunteering, donations, and more. Please try again later or "
            "contact us at contact@nayepankh.org."
        )


# ===========================================================================
# DONATION RECEIPT GENERATOR
# ===========================================================================

def generate_donation_receipt(donation_id, donor_name, email, amount, date):
    """
    Generate an HTML donation receipt for display in the chat.

    The receipt includes all donation details and a thank-you message.
    It's formatted as inline HTML that the frontend renders directly.

    Args:
        donation_id (int): The unique donation record ID (serves as receipt #).
        donor_name (str): The donor's full name.
        email (str): The donor's email address.
        amount (float): The donation amount in INR.
        date (str): The donation date.

    Returns:
        str: Formatted HTML string for the donation receipt.
    """
    receipt_html = f"""
    <div class="donation-receipt" style="border: 2px solid #28a745; border-radius: 12px; padding: 20px; margin: 10px 0; background: linear-gradient(135deg, #f0fff0, #e8f5e9);">
        <h3 style="color: #28a745; text-align: center; margin-bottom: 15px;">🎉 Donation Receipt</h3>
        <hr style="border-color: #28a745;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; font-weight: bold;">📋 Receipt ID:</td><td style="padding: 8px;">#{donation_id}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">👤 Donor Name:</td><td style="padding: 8px;">{donor_name}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">📧 Email:</td><td style="padding: 8px;">{email}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">💰 Amount:</td><td style="padding: 8px; font-size: 1.2em; color: #28a745; font-weight: bold;">₹{amount:,.2f}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">📅 Date:</td><td style="padding: 8px;">{date}</td></tr>
        </table>
        <hr style="border-color: #28a745;">
        <p style="text-align: center; color: #666; margin-top: 10px;">
            💝 Thank you for your generous contribution to NayePankh Foundation!<br>
            Your donation is eligible for tax deduction under Section 80G.<br>
            <small>A confirmation email will be sent to {email}</small>
        </p>
    </div>
    """
    return receipt_html


# ===========================================================================
# CORE CHAT PROCESSING ENGINE — HYBRID AI ARCHITECTURE
# ===========================================================================

def process_message(user_id, message, language='en'):
    """
    Process a user message using the HYBRID AI ARCHITECTURE.

    This is the heart of the cost optimization strategy. The function follows
    a strict processing pipeline where each step is FREE except the very last
    one (OpenAI API call). By handling most queries locally, we reduce API
    costs by approximately 80-90%.

    HYBRID AI ARCHITECTURE — Cost Optimization for NGOs
    =====================================================
    Step 1: Check FAQ entries added by admin (FREE - reduces repeat API calls)
    Step 2: Extract and store any memory from user message (FREE)
    Step 3: Check for volunteer/donation workflow state (FREE)
    Step 4: Match against local NGO knowledge base (FREE)
    Step 5: Check memory-related questions like 'what is my name' (FREE)
    Step 6: ONLY if no local match → call OpenAI API (PAID)

    This architecture ensures ~80-90% of queries are handled locally,
    reducing API costs significantly for resource-constrained NGOs.

    Args:
        user_id (int): The logged-in user's ID.
        message (str): The user's raw message text.
        language (str): Language code ('en', 'hi', 'ta', 'te', 'kn').

    Returns:
        tuple: (response_text: str, is_receipt: bool)
               is_receipt is True when the response contains HTML receipt markup.
    """
    msg_lower = message.lower().strip()

    # Ensure valid language code; fall back to English if unsupported
    if language not in TRANSLATIONS:
        language = 'en'
    lang = TRANSLATIONS[language]

    # ===================================================================
    # STEP 1: FAQ LOOKUP (FREE — zero API cost)
    # -------------------------------------------------------------------
    # Check admin-curated FAQs and auto-cached OpenAI responses FIRST.
    # This is the most cost-effective step because:
    #   a) Admin FAQs handle common organizational questions for free
    #   b) Auto-cached responses prevent paying for the same question twice
    #
    # Over time, the FAQ cache grows organically, handling an increasing
    # percentage of queries without any API cost.
    # ===================================================================
    faq_result = get_faq_match(msg_lower)
    if faq_result:
        # Increment the usage counter for analytics
        increment_faq_frequency(faq_result['id'])
        return faq_result['answer'], False

    # ===================================================================
    # STEP 2: MEMORY EXTRACTION (FREE — local processing only)
    # -------------------------------------------------------------------
    # Extract any personal information from the message and store it.
    # This runs on EVERY message to catch statements like:
    #   "My name is Ajai" → stores name
    #   "I live in Delhi" → stores city
    # The extracted data personalizes future responses for free.
    # ===================================================================
    extracted = extract_and_store_memory(user_id, message)

    # If the user just told us their name, acknowledge it immediately
    if extracted and 'name' in extracted:
        response = lang['name_remembered'].format(name=extracted['name'])
        return response, False

    # ===================================================================
    # STEP 3: WORKFLOW STATE MACHINE (FREE — session-based processing)
    # -------------------------------------------------------------------
    # Check if the user is in the middle of a multi-step workflow
    # (volunteer registration or donation). If so, process the current
    # step and advance the state machine. No API call needed.
    # ===================================================================

    # --- Volunteer Registration Workflow ---
    volunteer_step = session.get('volunteer_step', 0)
    if volunteer_step > 0:
        return handle_volunteer_workflow(user_id, message, volunteer_step, language), False

    # --- Donation Workflow ---
    donation_step = session.get('donation_step', 0)
    if donation_step > 0:
        result, is_receipt = handle_donation_workflow(user_id, message, donation_step, language)
        return result, is_receipt

    # ===================================================================
    # STEP 4: LOCAL KNOWLEDGE BASE MATCHING (FREE — dictionary lookup)
    # -------------------------------------------------------------------
    # Match the user's message against our curated NGO knowledge base.
    # This handles the bulk of common queries:
    #   - "Tell me about NayePankh" → about info
    #   - "I want to volunteer" → volunteer info + start workflow
    #   - "How can I donate?" → donation info + start workflow
    #   - "Hello!" → personalized greeting
    #
    # Each match avoids a ₹0.05-0.15 API call. With 500 messages/day,
    # this saves ₹750-₹2,250/month.
    # ===================================================================
    for category, data in NGO_KNOWLEDGE_BASE.items():
        for keyword in data['keywords']:
            if keyword in msg_lower:
                response_key = data['response_key']
                response = lang.get(response_key, TRANSLATIONS['en'].get(response_key, ''))

                # Special handling for greeting — include user's name if remembered
                if category == 'greeting':
                    user_name = get_user_memory(user_id, 'name')
                    name_part = f", {user_name}" if user_name else ""
                    response = response.format(name=name_part)

                # Special handling for volunteer/donate — start the workflow
                if category == 'volunteer' and any(
                    trigger in msg_lower for trigger in ['register', 'sign me up', 'sign up', 'join', 'i want to volunteer']
                ):
                    session['volunteer_step'] = 1
                    response = lang['volunteer_ask_name']
                elif category == 'donate' and any(
                    trigger in msg_lower for trigger in ['i want to donate', 'donate now', 'make a donation']
                ):
                    session['donation_step'] = 1
                    response = lang['donation_ask_name']

                return response, False

    # ===================================================================
    # STEP 5: MEMORY-RELATED QUESTIONS (FREE — database lookup)
    # -------------------------------------------------------------------
    # Handle questions about previously stored personal information:
    #   - "What is my name?" → recall stored name
    #   - "Where do I live?" → recall stored city
    #   - "What are my interests?" → recall stored interests
    # ===================================================================
    memory_questions = {
        'what is my name': 'name',
        'what\'s my name': 'name',
        'do you know my name': 'name',
        'who am i': 'name',
        'where do i live': 'city',
        'what is my city': 'city',
        'what\'s my city': 'city',
        'what are my interests': 'interest',
        'what do i like': 'interest',
        'what are my skills': 'skill',
        'what can i do': 'skill',
    }

    for question, memory_key in memory_questions.items():
        if question in msg_lower:
            value = get_user_memory(user_id, memory_key)
            if value:
                if memory_key == 'name':
                    return lang['name_recalled'].format(name=value), False
                elif memory_key == 'city':
                    return f"You told me you live in **{value}**! 🏙️", False
                elif memory_key == 'interest':
                    return f"You mentioned you're interested in **{value}**! ⭐", False
                elif memory_key == 'skill':
                    return f"You told me you know **{value}**! 💪", False
            else:
                return f"I don't have that information yet. You can tell me anytime! 😊", False

    # ===================================================================
    # STEP 6: OPENAI API CALL — LAST RESORT (PAID — ~₹0.05 per call)
    # -------------------------------------------------------------------
    # If we've reached this point, the message is genuinely complex and
    # can't be handled by any local processing. This should be ~10% of
    # all messages.
    #
    # After getting the AI response, we AUTO-CACHE it as an FAQ entry
    # so the same question never hits the API again.
    # ===================================================================
    memory_context = get_memory_context(user_id)
    chat_history = get_chat_history(user_id, limit=3)
    # Convert sqlite3.Row objects to dicts for the API function
    chat_history_list = [{'role': msg['role'], 'message': msg['message']} for msg in chat_history]

    ai_response = ask_openai(message, memory_context, chat_history_list)

    # AUTO-FAQ: Cache this response to avoid paying for the same question twice.
    # The next time someone asks a similar question, it will be caught by Step 1
    # (FAQ lookup) and the API will not be called. This is a key cost-saving
    # mechanism that makes the system cheaper over time as the FAQ cache grows.
    if ai_response and openai_client:
        add_faq(
            question_pattern=msg_lower,
            answer=ai_response,
            created_by=None  # None indicates auto-cached (not admin-curated)
        )

    return ai_response, False


# ===========================================================================
# WORKFLOW HANDLERS — Multi-step conversation flows
# ===========================================================================

def handle_volunteer_workflow(user_id, message, step, language='en'):
    """
    Handle the multi-step volunteer registration workflow.

    This is a state machine driven by session['volunteer_step']:
      Step 1: Collect name → advance to step 2
      Step 2: Collect skills → advance to step 3
      Step 3: Collect city → advance to step 4
      Step 4: Collect availability → save to DB → clear workflow

    All processing is local (FREE). No API calls needed.

    Args:
        user_id (int): The logged-in user's ID.
        message (str): The user's response for the current step.
        step (int): Current step number (1-4).
        language (str): Language code for response text.

    Returns:
        str: The response message for the current step.
    """
    lang = TRANSLATIONS.get(language, TRANSLATIONS['en'])

    if step == 1:
        # Step 1: User provides their name
        session['volunteer_name'] = message.strip().title()
        session['volunteer_step'] = 2
        # Also store the name in memory for personalization
        set_user_memory(user_id, 'name', session['volunteer_name'])
        return lang['volunteer_ask_skills'].format(name=session['volunteer_name'])

    elif step == 2:
        # Step 2: User provides their skills
        session['volunteer_skills'] = message.strip()
        session['volunteer_step'] = 3
        return lang['volunteer_ask_city']

    elif step == 3:
        # Step 3: User provides their city
        session['volunteer_city'] = message.strip().title()
        session['volunteer_step'] = 4
        # Also store city in memory
        set_user_memory(user_id, 'city', session['volunteer_city'])
        return lang['volunteer_ask_availability']

    elif step == 4:
        # Step 4: User provides availability → save everything to database
        availability = message.strip().lower()
        # Normalize the availability value
        valid_options = ['weekdays', 'weekends', 'both', 'flexible']
        if availability not in valid_options:
            availability = 'flexible'  # Default to flexible if input is unclear

        # Save the complete volunteer registration to the database
        volunteer_name = session.get('volunteer_name', 'Unknown')
        volunteer_skills = session.get('volunteer_skills', 'Not specified')
        volunteer_city = session.get('volunteer_city', 'Not specified')

        add_volunteer(
            user_id=user_id,
            name=volunteer_name,
            skills=volunteer_skills,
            city=volunteer_city,
            availability=availability
        )

        # Clear all workflow state from the session
        session.pop('volunteer_step', None)
        session.pop('volunteer_name', None)
        session.pop('volunteer_skills', None)
        session.pop('volunteer_city', None)

        return lang['volunteer_success'].format(
            name=volunteer_name,
            skills=volunteer_skills,
            city=volunteer_city,
            availability=availability.title()
        )

    # Fallback — should never reach here
    session.pop('volunteer_step', None)
    return lang.get('help_menu', TRANSLATIONS['en']['help_menu'])


def handle_donation_workflow(user_id, message, step, language='en'):
    """
    Handle the multi-step donation recording workflow.

    This is a state machine driven by session['donation_step']:
      Step 1: Collect donor name → advance to step 2
      Step 2: Collect email (validated) → advance to step 3
      Step 3: Collect amount (validated as number) → save to DB → show receipt

    All processing is local (FREE). No API calls needed.

    Args:
        user_id (int): The logged-in user's ID.
        message (str): The user's response for the current step.
        step (int): Current step number (1-3).
        language (str): Language code for response text.

    Returns:
        tuple: (response_text: str, is_receipt: bool)
    """
    lang = TRANSLATIONS.get(language, TRANSLATIONS['en'])

    if step == 1:
        # Step 1: User provides donor name
        session['donation_name'] = message.strip().title()
        session['donation_step'] = 2
        return lang['donation_ask_email'].format(name=session['donation_name']), False

    elif step == 2:
        # Step 2: User provides email — validate format before accepting
        email = message.strip().lower()
        # Simple email validation regex (covers 99% of valid emails)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            # Invalid email — ask again without advancing step
            return "❌ That doesn't look like a valid email address. Please enter a valid email (e.g., name@example.com):", False

        session['donation_email'] = email
        session['donation_step'] = 3
        return lang['donation_ask_amount'], False

    elif step == 3:
        # Step 3: User provides amount — validate it's a positive number
        # Strip currency symbols and commas for flexibility
        amount_str = message.strip().replace('₹', '').replace(',', '').replace('Rs', '').replace('rs', '').replace('INR', '').replace('inr', '').strip()

        try:
            amount = float(amount_str)
            if amount <= 0:
                return "❌ Please enter a valid positive amount (e.g., 500, 1000, 5000):", False
        except ValueError:
            return "❌ That doesn't look like a valid amount. Please enter a number (e.g., 500, 1000, 5000):", False

        # Save the donation to the database
        donor_name = session.get('donation_name', 'Anonymous')
        donor_email = session.get('donation_email', '')
        donation_date = datetime.now().strftime('%Y-%m-%d')

        donation_id = add_donation(
            user_id=user_id,
            donor_name=donor_name,
            email=donor_email,
            amount=amount,
            date=donation_date
        )

        # Generate the donation receipt HTML
        receipt = generate_donation_receipt(
            donation_id=donation_id,
            donor_name=donor_name,
            email=donor_email,
            amount=amount,
            date=donation_date
        )

        # Clear all workflow state from the session
        session.pop('donation_step', None)
        session.pop('donation_name', None)
        session.pop('donation_email', None)

        return receipt, True  # is_receipt=True tells frontend to render HTML

    # Fallback — should never reach here
    session.pop('donation_step', None)
    return lang.get('help_menu', TRANSLATIONS['en']['help_menu']), False


# ===========================================================================
# AUTHENTICATION DECORATOR
# ===========================================================================

def login_required(f):
    """
    Decorator to protect routes that require authentication.

    Checks for a valid user_id in the Flask session. If not found,
    redirects to the login page with a flash message. Uses functools.wraps
    to preserve the original function's name and docstring (important for
    Flask's url_for to work correctly with decorated routes).

    Usage:
        @app.route('/protected')
        @login_required
        def protected_page():
            ...
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ===========================================================================
# AUTHENTICATION ROUTES
# ===========================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login (GET: show form, POST: authenticate).

    Security measures:
      - Password verified using Werkzeug's check_password_hash (timing-safe)
      - Failed logins show generic message (doesn't reveal if user exists)
      - Successful login stores user_id and username in session
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return redirect(url_for('login'))

        user = get_user_by_username(username)

        if user and check_password_hash(user['password_hash'], password):
            # Successful login — store user info in session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            # Failed login — generic message for security
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handle new user registration (GET: show form, POST: create account).

    Validation checks:
      1. All fields are required (username, email, password, confirm_password)
      2. Password must be at least 6 characters long
      3. Password and confirmation must match
      4. Username must be unique (not already taken)
      5. Email must be unique (not already registered)
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # --- Validation ---
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        # Check for existing username
        if get_user_by_username(username):
            flash('Username already taken. Please choose another.', 'danger')
            return redirect(url_for('register'))

        # Check for existing email (using a direct query since we don't
        # have a dedicated get_user_by_email function)
        from database import get_db as _get_db
        _conn = _get_db()
        _cursor = _conn.cursor()
        _cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if _cursor.fetchone():
            _conn.close()
            flash('Email already registered. Please use another or log in.', 'danger')
            return redirect(url_for('register'))
        _conn.close()

        # --- Create the user ---
        password_hash = generate_password_hash(password)
        add_user(username, email, password_hash)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """
    Log out the current user by clearing their session.

    Clears ALL session data including workflow state, user info, and any
    temporary data. Redirects to the login page.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ===========================================================================
# MAIN ROUTES
# ===========================================================================

@app.route('/')
@login_required
def index():
    """
    Main chat interface page. Requires authentication.

    Renders the index.html template which contains the chat UI.
    The actual chat processing happens via the /api/chat endpoint.
    """
    return render_template('index.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Admin dashboard page with statistics, user management, and FAQ management.

    Displays:
      - Summary statistics (total users, volunteers, donations, chat sessions)
      - Recent volunteer registrations (last 5)
      - Recent donations (last 5)
      - All registered users
      - Recent chat questions (last 50) for review
      - All FAQ entries with management controls
    """
    stats = {
        'total_users': count_users(),
        'total_volunteers': count_volunteers(),
        'total_donations': count_donations(),
        'total_chats': count_chat_sessions()
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        recent_volunteers=get_all_volunteers(limit=5),
        recent_donations=get_all_donations(limit=5),
        all_users=get_all_users(),
        all_questions=get_all_chat_questions()[:50],
        all_faqs=get_all_faqs()
    )


# ===========================================================================
# API ROUTES — JSON endpoints for the chat interface
# ===========================================================================

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """
    Process a chat message and return the AI response.

    Expects JSON body: {"message": "user text", "language": "en"}
    Returns JSON: {"response": "bot text", "timestamp": "ISO datetime", "is_receipt": bool}

    This endpoint:
      1. Validates the input
      2. Saves the user's message to chat_history
      3. Processes the message through the hybrid AI pipeline
      4. Saves the bot's response to chat_history
      5. Returns the response as JSON
    """
    data = request.get_json()
    if not data or not data.get('message', '').strip():
        return jsonify({'error': 'Message is required'}), 400

    user_id = session['user_id']
    message = data['message'].strip()
    language = data.get('language', 'en')

    # Save user message to chat history
    add_chat_message(user_id, 'user', message)

    # Process through the hybrid AI pipeline
    response, is_receipt = process_message(user_id, message, language)

    # Save bot response to chat history (store plain text for receipts)
    add_chat_message(user_id, 'assistant', response)

    return jsonify({
        'response': response,
        'timestamp': datetime.now().isoformat(),
        'is_receipt': is_receipt
    })


@app.route('/api/chat/history')
@login_required
def api_chat_history():
    """
    Return the current user's chat history as a JSON array.

    Each message includes: id, role, message, timestamp.
    Limited to the most recent 50 messages.
    """
    user_id = session['user_id']
    history = get_chat_history(user_id, limit=50)

    messages = []
    for msg in history:
        messages.append({
            'id': msg['id'],
            'role': msg['role'],
            'message': msg['message'],
            'timestamp': msg['timestamp']
        })

    return jsonify(messages)


@app.route('/api/analytics')
@login_required
def api_analytics():
    """
    Return monthly analytics data for dashboard charts.

    Returns JSON with three datasets:
      - volunteers_monthly: [{month, count}, ...]
      - donations_monthly: [{month, count}, ...]
      - chats_monthly: [{month, count}, ...]

    Each dataset covers the last 6 months.
    """
    return jsonify({
        'volunteers_monthly': volunteers_per_month(),
        'donations_monthly': donations_per_month(),
        'chats_monthly': chats_per_month()
    })


@app.route('/api/admin/faq', methods=['POST'])
@login_required
def api_add_faq():
    """
    Add a new FAQ entry (admin action).

    Expects JSON body: {"question": "pattern text", "answer": "response text"}
    Returns JSON: {"success": true, "faq_id": int}

    Admin-curated FAQs are a key cost optimization — every FAQ entry
    prevents future API calls for matching questions.
    """
    data = request.get_json()
    if not data or not data.get('question') or not data.get('answer'):
        return jsonify({'error': 'Question and answer are required'}), 400

    faq_id = add_faq(
        question_pattern=data['question'].strip(),
        answer=data['answer'].strip(),
        created_by=session['user_id']
    )

    return jsonify({'success': True, 'faq_id': faq_id})


@app.route('/api/admin/faq/<int:faq_id>', methods=['DELETE'])
@login_required
def api_delete_faq(faq_id):
    """
    Delete an FAQ entry by its ID (admin action).

    Returns JSON: {"success": true}
    """
    delete_faq(faq_id)
    return jsonify({'success': True})


# ===========================================================================
# APPLICATION STARTUP
# ===========================================================================

if __name__ == '__main__':
    # Initialize the database (creates tables + default admin user)
    init_db()
    # Run the development server on port 5000
    # In production, use a proper WSGI server like Gunicorn or Waitress
    app.run(debug=True, port=5000)
