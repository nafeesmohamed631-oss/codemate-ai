# CodeMate AI – Personalized Code Learning & Document Assistant

Full-stack academic/demo implementation for the supplied CodeMate AI specification.

Core rule: USER CHOOSES THE LEVEL -> AI EXPLAINS AT THAT LEVEL.
No automatic programming-skill prediction is implemented.

## Backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload

## Frontend
cd frontend
npm install
npm run dev

Backend: http://127.0.0.1:8000
Frontend: http://localhost:5173

Set LLM_API_KEY in backend/.env for an OpenAI-compatible LLM. The backend also has a no-LLM fallback that shows retrieved source context.
