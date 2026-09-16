from pathlib import Path
import uuid, json
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import User, Project, ProjectFile, KnowledgePreference, ChatSession, ChatMessage
from typing import Optional
from .schemas import AuthIn, RegisterIn, PreferenceIn, ChatIn
from .security import hash_password, verify_password, token, current_user
from .services import extract, build_index, search, prompt, llm, detect_technologies, generate_local_tutor_response
from .config import settings

Base.metadata.create_all(bind=engine)
Path(settings.upload_dir).mkdir(parents=True,exist_ok=True)
app=FastAPI(title="CodeMate AI API")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
                   allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status":"ok"}

@app.post("/api/auth/register")
def register(d:RegisterIn,db:Session=Depends(get_db)):
    if d.confirm_password and d.password != d.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if db.query(User).filter_by(email=d.email).first(): raise HTTPException(409,"Email already registered")
    u=User(email=d.email,name=d.name or "",password_hash=hash_password(d.password)); db.add(u); db.commit(); db.refresh(u)
    return {"message":"Registration successful","access_token":token(u.id),"token_type":"bearer"}

@app.post("/api/auth/login")
def login(d:AuthIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=d.email).first()
    if not u or not verify_password(d.password,u.password_hash): raise HTTPException(401,"Invalid credentials")
    return {"access_token":token(u.id),"token_type":"bearer","name":u.name or u.email.split("@")[0]}

@app.get("/api/preferences")
def preferences(db:Session=Depends(get_db),u=Depends(current_user)):
    return db.query(KnowledgePreference).filter_by(user_id=u.id).all()

@app.put("/api/preferences")
def save_pref(d:PreferenceIn,db:Session=Depends(get_db),u=Depends(current_user)):
    p=db.query(KnowledgePreference).filter_by(user_id=u.id,technology=d.technology).first()
    if not p: p=KnowledgePreference(user_id=u.id,technology=d.technology); db.add(p)
    p.knowledge_level=d.knowledge_level; p.language=d.language; p.format=d.format
    db.commit(); db.refresh(p); return p

@app.post("/api/projects/upload")
async def upload(file:UploadFile=File(...),technology:Optional[str]=Form(None),db:Session=Depends(get_db),u=Depends(current_user)):
    data=await file.read()
    if len(data)>settings.max_file_mb*1024*1024: raise HTTPException(413,"File too large")
    try: kind,items=extract(file.filename,data)
    except ValueError as e: raise HTTPException(400,str(e))
    detected = detect_technologies(items, file.filename)
    chosen_tech = technology or (detected[0] if detected else "C")
    pid=uuid.uuid4().hex; folder=Path(settings.upload_dir)/str(u.id)/pid; folder.mkdir(parents=True)
    p=Project(name=Path(file.filename).stem,original_name=file.filename,kind=kind,
              technology=chosen_tech,
              file_count=len(items),line_count=sum(len(x[1].splitlines()) for x in items),
              root_path=str(folder),owner_id=u.id,status="processing")
    db.add(p); db.commit(); db.refresh(p)
    for path,text,lang in items:
        eff_lang = chosen_tech if lang in ("PDF","DOCX","Unknown") else lang
        db.add(ProjectFile(project_id=p.id,relative_path=path,language=eff_lang,content=text,line_count=len(text.splitlines())))
    db.commit(); build_index(str(folder),items)
    p.status="ready"; db.commit(); db.refresh(p)
    return {"id":p.id,"name":p.name,"original_name":p.original_name,"kind":p.kind,
            "technology":p.technology,"detected_languages":detected,
            "file_count":p.file_count,"line_count":p.line_count,"status":p.status}

def own(db,u,pid):
    p=db.get(Project,pid)
    if not p or p.owner_id!=u.id: raise HTTPException(404,"Project not found")
    return p

@app.get("/api/projects")
def projects(db:Session=Depends(get_db),u=Depends(current_user)):
    return [{"id":p.id,"name":p.name,"technology":p.technology,"file_count":p.file_count,
             "line_count":p.line_count,"status":p.status} for p in db.query(Project).filter_by(owner_id=u.id).all()]

@app.get("/api/projects/{pid}")
def get_project(pid:int,db:Session=Depends(get_db),u=Depends(current_user)):
    p=own(db,u,pid)
    detected = [p.technology] if p.technology not in ("Multi-file project","Unknown") else []
    for f in p.files:
        if f.language and f.language not in ("PDF","DOCX","Unknown","Multi-file project") and f.language not in detected:
            detected.append(f.language)
    if not detected: detected = ["C"]
    return {"id":p.id,"name":p.name,"original_name":p.original_name,"kind":p.kind,
            "technology":p.technology,"detected_languages":detected,"file_count":p.file_count,
            "line_count":p.line_count,"status":p.status}

@app.get("/api/projects/{pid}/files")
def files(pid:int,db:Session=Depends(get_db),u=Depends(current_user)):
    p=own(db,u,pid)
    return [{"id":f.id,"path":f.relative_path,"language":f.language,"line_count":f.line_count} for f in p.files]

@app.get("/api/projects/{pid}/files/{fid}")
def file(pid:int,fid:int,db:Session=Depends(get_db),u=Depends(current_user)):
    p=own(db,u,pid); f=db.get(ProjectFile,fid)
    if not f or f.project_id!=p.id: raise HTTPException(404,"File not found")
    return {"id":f.id,"path":f.relative_path,"language":f.language,"content":f.content}

@app.post("/api/chat/ask")
async def ask(d:ChatIn,db:Session=Depends(get_db),u=Depends(current_user)):
    p=own(db,u,d.project_id)
    rs=[]
    
    # 1. Direct selected code passed from file modal
    if d.selected_code and d.selected_code.strip():
        rs.append({
            "source": f"{p.original_name} (Selected Page/Snippet)",
            "text": d.selected_code.strip(),
            "start_line": 1,
            "end_line": len(d.selected_code.strip().splitlines()),
            "score": 1.0
        })

    # 2. Check if question explicitly mentions a specific page (e.g. '20th page', 'page 20', 'page-20', '#page-20')
    import re
    page_match = re.search(r'(?:#page-|page-|page\s+|pg\s+)(\d+)', d.question, re.IGNORECASE)
    if not page_match:
        page_match = re.search(r'(\d+)(?:st|nd|rd|th)?\s+page', d.question, re.IGNORECASE)
    
    target_file = None
    if page_match:
        page_num = int(page_match.group(1))
        target_file = db.query(ProjectFile).filter(
            ProjectFile.project_id == p.id,
            ProjectFile.relative_path.like(f"%#page-{page_num}")
        ).first()

    if not target_file:
        for f in p.files:
            if f.relative_path.lower() in d.question.lower() or Path(f.relative_path).name.lower() in d.question.lower():
                target_file = f
                break

    if target_file and target_file.content:
        # Avoid duplicate if already added
        if not any(r["text"] == target_file.content for r in rs):
            rs.insert(0, {
                "source": target_file.relative_path,
                "text": target_file.content,
                "start_line": 1,
                "end_line": len(target_file.content.splitlines()),
                "score": 1.0
            })

    # 3. Augment with vector search results
    search_rs = search(p.root_path, d.question, 6)
    for s in search_rs:
        if not any(r["source"] == s["source"] and r.get("text") == s.get("text") for r in rs):
            rs.append(s)

    ctx="\n\n---\n\n".join(f"SOURCE {r['source']} LINES {r['start_line']}-{r['end_line']}\n{r['text']}" for r in rs)
    answer=await llm(prompt(d.question,ctx,p.technology,d.knowledge_level,d.language,d.format,d.selected_code))
    if not answer:
        answer=generate_local_tutor_response(d.question,ctx,p.technology,d.knowledge_level,d.format,d.language,rs,p.original_name)
    s=ChatSession(project_id=p.id,title=d.question[:80]); db.add(s); db.commit(); db.refresh(s)
    db.add(ChatMessage(session_id=s.id,role="user",content=d.question,knowledge_level=d.knowledge_level,language=d.language,format=d.format))
    db.add(ChatMessage(session_id=s.id,role="assistant",content=answer,knowledge_level=d.knowledge_level,language=d.language,format=d.format,
                       sources=json.dumps([{"source":r["source"],"start_line":r["start_line"],"end_line":r["end_line"]} for r in rs])))
    db.commit()
    return {"answer":answer,"session_id":s.id,"sources":rs}

@app.post("/api/documents/preview")
async def document_preview(file:UploadFile=File(...),u=Depends(current_user)):
    data=await file.read()
    try: kind,items=extract(file.filename,data)
    except ValueError as e: raise HTTPException(400,str(e))
    return {"name":file.filename,"kind":kind,"items":[{"source":x[0],"type":x[2],"characters":len(x[1])} for x in items]}
