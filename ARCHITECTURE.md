# AI-Powered Paraguay Newcomer App - System Architecture

## 🎯 Project Overview
**Goal**: Help newcomers (mainly Brazilians) get AI-assisted guidance on Paraguayan bureaucracy, documents, and local adaptation via a chat-based interface with localized information.

**Tech Stack**: Django Backend + Next.js Frontend + PostgreSQL with pgvector

---

## 🏗️ System Architecture

### Backend (Django) - Core AI & Data Layer
**Location**: `/cheguia-backend/`
**Purpose**: Handle AI processing, data management, and business logic

#### Apps Structure:
```
cheguia-backend/
├── ai/           # AI processing, embeddings, RAG
├── chat/         # Chat history, sessions, messages
├── documents/    # Document templates, knowledge base
├── users/        # User management, authentication
└── api/          # REST API endpoints
```

#### Core Responsibilities:
- **AI Processing**: LangChain + OpenAI integration
- **RAG System**: Document retrieval and context building
- **Chat Management**: Message history, sessions, user context
- **Document Templates**: Dynamic document generation
- **User Management**: Authentication, progress tracking
- **Knowledge Base**: Document storage and vector embeddings

### Frontend (Next.js) - User Interface
**Location**: `/cheguia-frontend/` (to be created)
**Purpose**: User interface and user experience

#### Features:
- Chat interface with message bubbles
- Document template generator
- Progress tracking dashboard
- Language switcher (Spanish/Portuguese)
- User authentication UI
- Mobile-responsive design

### Database (PostgreSQL + pgvector)
**Purpose**: Store all application data including vector embeddings

#### Key Tables:
- **Users**: Authentication, preferences, subscription status
- **Chats**: Chat sessions and message history
- **Documents**: Knowledge base documents and metadata
- **Document_embeddings**: Vector embeddings for RAG
- **Templates**: Document templates for generation
- **User_progress**: Checklist progress and completion

---

## 🔧 Technical Implementation

### Django Backend Configuration

#### Settings Updates Needed:
```python
# settings.py additions
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'ai',
    'chat', 
    'documents',
    'users',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'paraguay_guide',
        'USER': 'postgres',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# CORS for Next.js frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Next.js dev
    "https://yourdomain.com", # Production
]
```

#### API Endpoints Structure:
```
/api/
├── auth/           # Authentication endpoints
├── chat/           # Chat functionality
├── documents/      # Document management
├── templates/      # Template generation
├── users/          # User management
└── ai/             # AI processing endpoints
```

### PostgreSQL + pgvector Setup

#### Required Extensions:
```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

#### Key Database Schema:
```sql
-- Documents table with vector embeddings
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    source_url VARCHAR(1000),
    document_type VARCHAR(100),
    language VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    embedding vector(1536) -- OpenAI embedding dimension
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id),
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🚀 Development Phases

### Phase 1: Foundation (Week 1)
**Backend Tasks:**
- [ ] Set up PostgreSQL with pgvector
- [ ] Configure Django settings for new apps
- [ ] Create basic models for users, chats, documents
- [ ] Set up LangChain + OpenAI integration
- [ ] Create basic chat API endpoint

**Frontend Tasks:**
- [ ] Create Next.js project with TypeScript
- [ ] Set up Tailwind CSS and basic UI components
- [ ] Create chat interface mockup
- [ ] Connect to Django API

### Phase 2: RAG Integration (Week 2)
**Backend Tasks:**
- [ ] Implement document embedding system
- [ ] Create RAG pipeline with vector similarity search
- [ ] Add document ingestion from Paraguay sources
- [ ] Implement source citation in responses
- [ ] Add language detection and localization

**Frontend Tasks:**
- [ ] Enhance chat UI with message bubbles
- [ ] Add source citations display
- [ ] Implement language switcher
- [ ] Add loading states and error handling

### Phase 3: Document Features (Week 3)
**Backend Tasks:**
- [ ] Create document template system
- [ ] Implement dynamic template filling
- [ ] Add checklist generation based on visa types
- [ ] Create translation service (Portuguese ↔ Spanish)

**Frontend Tasks:**
- [ ] Build document template interface
- [ ] Add checklist progress tracking
- [ ] Implement template download functionality
- [ ] Create progress dashboard

### Phase 4: Polish & Launch (Week 4)
**Backend Tasks:**
- [ ] Add user authentication (Supabase or Django Auth)
- [ ] Implement subscription/premium features
- [ ] Add chat history and user progress storage
- [ ] Set up production database and environment

**Frontend Tasks:**
- [ ] Add authentication UI
- [ ] Implement premium feature gates
- [ ] Add feedback system (thumbs up/down)
- [ ] Mobile optimization and testing

---

## 🔐 Environment Variables

### Django Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/paraguay_guide

# OpenAI
OPENAI_API_KEY=your_openai_key

# Django
SECRET_KEY=your_django_secret_key
DEBUG=True

# CORS
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Supabase (if using for auth)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

### Next.js Frontend (.env.local)
```bash
# API
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Supabase
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

# Stripe (for payments)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=your_stripe_key
```

---

## 📁 Project Structure

```
paraguay-project/
├── cheguia-backend/          # Django backend
│   ├── ai/                   # AI processing
│   ├── chat/                 # Chat functionality  
│   ├── documents/            # Document management
│   ├── users/                # User management
│   ├── api/                  # REST API
│   ├── cheguia/              # Django settings
│   ├── requirements.txt      # Python dependencies
│   └── manage.py
├── cheguia-frontend/         # Next.js frontend (to create)
│   ├── app/                  # App Router
│   ├── components/           # React components
│   ├── lib/                  # Utilities
│   ├── public/               # Static assets
│   └── package.json
├── data/                     # Knowledge base documents
│   ├── migraciones/          # Immigration docs
│   ├── set/                  # Tax authority docs
│   └── ande/                 # Electric company docs
└── docs/                     # Documentation
    └── ARCHITECTURE.md       # This file
```

---

## 🔄 Data Flow

1. **User Input** → Next.js Frontend
2. **API Request** → Django Backend
3. **Query Processing** → AI App (LangChain)
4. **Document Retrieval** → RAG System (pgvector)
5. **Context Building** → Relevant documents + embeddings
6. **AI Response** → OpenAI with context
7. **Response** → Django → Next.js → User

---

## 🎯 Success Metrics

- **Response Accuracy**: AI provides correct, source-cited information
- **User Engagement**: Users complete document checklists
- **Performance**: <2s response time for chat queries
- **Scalability**: Handle 100+ concurrent users
- **Localization**: Seamless Spanish/Portuguese experience

---

## 🚀 Deployment Strategy

### Development
- Django: `python manage.py runserver`
- Next.js: `npm run dev`
- PostgreSQL: Local instance with pgvector

### Production
- Django: AWS EC2 or Railway
- Next.js: Vercel deployment
- PostgreSQL: AWS RDS with pgvector extension
- Static Files: AWS S3
- Domain: Custom domain with SSL

---

*This architecture document should be updated as the project evolves and requirements change.*
