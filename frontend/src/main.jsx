import React, { useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Sparkles,
  Upload,
  Send,
  Sun,
  Moon,
  Code2,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  FileText,
  BookOpen,
  HelpCircle,
  RotateCcw,
  Sliders
} from "lucide-react";
import "./style.css";

const API = "http://127.0.0.1:8000/api";
const ALL_TECH = ["C", "C++", "Java", "Python", "HTML", "CSS", "JavaScript", "C#", "React / JSX", "Node.js", "Express.js"];
const LANG = ["English", "Tamil", "Hindi"];
const FMT = [
  { id: "block_by_block", label: "🧱 Block-by-Block (Syntax & Code breakdown - Recommended for 1st-Year)" },
  { id: "points", label: "📝 Points (Point-by-point bullet list - Best for theory)" },
  { id: "paragraph", label: "📄 Paragraphs (Para-by-para detailed explanations)" },
  { id: "paragraph_and_points", label: "📑 Paragraph and Points" },
  { id: "step_by_step", label: "🪜 Step-by-Step Logic" },
];

const authHeader = () => {
  const t = localStorage.getItem("cm_token");
  return t ? { Authorization: "Bearer " + t } : {};
};

async function api(path, options = {}) {
  const isForm = options.body instanceof FormData;
  const headers = isForm ? {} : { "Content-Type": "application/json" };
  const res = await fetch(API + path, {
    ...options,
    headers: { ...headers, ...authHeader() },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Markdown formatter for AI Tutor responses
function FormattedMessage({ text }) {
  if (!text) return null;

  // Split by code blocks
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <div>
      {parts.map((part, idx) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).trim().split("\n");
          const lang = lines[0].trim();
          const code = (lang && !lang.includes(" ") && lines.length > 1 ? lines.slice(1) : lines).join("\n");
          return (
            <pre key={idx}>
              {lang && <small style={{ display: "block", color: "#8b7cff", marginBottom: 6 }}>{lang}</small>}
              <code>{code}</code>
            </pre>
          );
        }

        // Parse lines for headers, lists, hr
        const lines = part.split("\n");
        return (
          <div key={idx}>
            {lines.map((line, lIdx) => {
              const trimmed = line.trim();
              if (trimmed.startsWith("### ")) {
                return <h3 key={lIdx}>{trimmed.slice(4)}</h3>;
              }
              if (trimmed.startsWith("#### ")) {
                return <h4 key={lIdx}>{trimmed.slice(5)}</h4>;
              }
              if (trimmed === "---") {
                return <hr key={lIdx} />;
              }
              if (trimmed.startsWith("• ") || trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                return (
                  <div key={lIdx} style={{ paddingLeft: 14, margin: "4px 0", display: "flex", gap: 6 }}>
                    <span style={{ color: "#7667f7" }}>•</span>
                    <span>{parseInline(trimmed.slice(2))}</span>
                  </div>
                );
              }
              if (!trimmed) {
                return <div key={lIdx} style={{ height: 8 }} />;
              }
              return <p key={lIdx} style={{ margin: "4px 0" }}>{parseInline(line)}</p>;
            })}
          </div>
        );
      })}
    </div>
  );
}

function parseInline(text) {
  // Parse **bold** and `code`
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((seg, i) => {
    if (seg.startsWith("**") && seg.endsWith("**")) {
      return <strong key={i}>{seg.slice(2, -2)}</strong>;
    }
    if (seg.startsWith("`") && seg.endsWith("`")) {
      return <code key={i}>{seg.slice(1, -1)}</code>;
    }
    return seg;
  });
}

function Login({ done }) {
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [err, setErr] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setSuccessMsg("");

    if (isRegister) {
      if (password !== confirmPassword) {
        setErr("Passwords do not match!");
        return;
      }
      try {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({ name, email, password, confirm_password: confirmPassword }),
        });
        setSuccessMsg("Account created successfully! Please log in.");
        setIsRegister(false);
        setPassword("");
        setConfirmPassword("");
      } catch (x) {
        try {
          const parsed = JSON.parse(x.message);
          setErr(parsed.detail || x.message);
        } catch {
          setErr(x.message);
        }
      }
    } else {
      try {
        const d = await api("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        localStorage.setItem("cm_token", d.access_token);
        if (d.name) localStorage.setItem("cm_user_name", d.name);
        done();
      } catch (x) {
        try {
          const parsed = JSON.parse(x.message);
          setErr(parsed.detail || "Invalid credentials");
        } catch {
          setErr(x.message);
        }
      }
    }
  }

  return (
    <main className="auth">
      <form className="authbox" onSubmit={handleSubmit}>
        <h1>
          <Sparkles color="#8b7cff" /> CodeMate AI
        </h1>
        <p>Personalized code learning designed for 1st & 2nd year students.</p>

        {successMsg && <div className="success-msg">{successMsg}</div>}
        {err && <small>{err}</small>}

        {isRegister && (
          <input
            placeholder="Full Name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        )}

        <input
          placeholder="Email address"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <input
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {isRegister && (
          <input
            placeholder="Confirm Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        )}

        <button type="submit">{isRegister ? "Create Account" : "Login"}</button>

        <a
          onClick={() => {
            setIsRegister(!isRegister);
            setErr("");
            setSuccessMsg("");
          }}
        >
          {isRegister ? "Already have an account? Login" : "Don't have an account? Register"}
        </a>
      </form>
    </main>
  );
}

function App() {
  const [dark, setDark] = useState(true);
  const [step, setStep] = useState("upload"); // "upload" | "knowledge" | "tutor"
  const [project, setProject] = useState(null);
  const [files, setFiles] = useState([]);
  const [viewingFile, setViewingFile] = useState(null);
  const [fileContent, setFileContent] = useState("");
  const [loadingFile, setLoadingFile] = useState(false);

  const [availableTechs, setAvailableTechs] = useState(["C"]);
  const [tech, setTech] = useState("C");
  const [prefs, setPrefs] = useState({});

  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatusText, setUploadStatusText] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState([]);
  const [loadingAsk, setLoadingAsk] = useState(false);
  const chatBottomRef = useRef(null);

  useEffect(() => {
    document.body.className = dark ? "dark" : "";
    api("/preferences")
      .then((a) => setPrefs(Object.fromEntries(a.map((x) => [x.technology, x]))))
      .catch(() => {});

    api("/projects")
      .then(async (list) => {
        if (list && list.length > 0) {
          const last = list[list.length - 1];
          try {
            const pDetails = await api(`/projects/${last.id}`);
            setProject(pDetails);
            const langs = pDetails.detected_languages && pDetails.detected_languages.length > 0
              ? pDetails.detected_languages
              : [pDetails.technology || "C"];
            setAvailableTechs(langs);
            setTech(langs[0]);
            const fList = await api(`/projects/${last.id}/files`);
            setFiles(fList);
            setUploadSuccess(true);
          } catch {}
        }
      })
      .catch(() => {});
  }, [dark]);

  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [msgs, loadingAsk]);

  const pref = prefs[tech] || {
    knowledge_level: 20,
    language: "English",
    format: "block_by_block",
  };

  async function handleLevelChange(val) {
    const updated = { ...prefs, [tech]: { ...pref, knowledge_level: +val } };
    setPrefs(updated);
    await api("/preferences", {
      method: "PUT",
      body: JSON.stringify({
        technology: tech,
        knowledge_level: +val,
        language: pref.language,
        format: pref.format,
      }),
    });
  }

  async function handleFormatChange(val) {
    const updated = { ...prefs, [tech]: { ...pref, format: val } };
    setPrefs(updated);
    await api("/preferences", {
      method: "PUT",
      body: JSON.stringify({
        technology: tech,
        knowledge_level: pref.knowledge_level,
        language: pref.language,
        format: val,
      }),
    });
  }

  async function handleLanguageChange(val) {
    const updated = { ...prefs, [tech]: { ...pref, language: val } };
    setPrefs(updated);
    await api("/preferences", {
      method: "PUT",
      body: JSON.stringify({
        technology: tech,
        knowledge_level: pref.knowledge_level,
        language: val,
        format: pref.format,
      }),
    });
  }

  // Upload handler with progress simulation and auto-navigation
  async function handleFileUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadSuccess(false);
    setUploadProgress(15);
    setUploadStatusText("Uploading learning material...");

    const progressTimer = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev < 45) {
          setUploadStatusText("Detecting programming languages & code structure...");
          return prev + 10;
        } else if (prev < 78) {
          setUploadStatusText("Indexing syntax & program blocks...");
          return prev + 6;
        } else if (prev < 90) {
          setUploadStatusText("Preparing AI Tutor knowledge base...");
          return prev + 2;
        }
        return prev;
      });
    }, 200);

    try {
      const fd = new FormData();
      fd.append("file", file);

      const p = await api("/projects/upload", { method: "POST", body: fd });
      clearInterval(progressTimer);
      setUploadProgress(100);
      setUploadStatusText("Analysis complete! Opening knowledge settings...");
      setProject(p);

      // Fetch files
      const fList = await api(`/projects/${p.id}/files`);
      setFiles(fList);

      // Determine detected technologies
      const langs = p.detected_languages && p.detected_languages.length > 0
        ? p.detected_languages
        : [p.technology && p.technology !== "Multi-file project" ? p.technology : "C"];

      setAvailableTechs(langs);
      setTech(langs[0]);
      setUploadSuccess(true);

      // Automatically advance to Step 2 (Knowledge Level) after short 600ms visual confirmation!
      setTimeout(() => {
        setStep("knowledge");
        setUploading(false);
        setUploadProgress(0);
      }, 600);
    } catch (err) {
      clearInterval(progressTimer);
      setUploading(false);
      setUploadProgress(0);
      alert("Upload failed: " + err.message);
    } finally {
      if (e.target) e.target.value = "";
    }
  }

  // Open file view modal
  async function inspectFile(f) {
    setViewingFile(f);
    setLoadingFile(true);
    try {
      const d = await api(`/projects/${project.id}/files/${f.id}`);
      setFileContent(d.content);
    } catch {
      setFileContent("Could not load file content.");
    } finally {
      setLoadingFile(false);
    }
  }

  // Ask AI Tutor
  async function askQuestion(questionText, selectedCode = null, overrideLevel = null) {
    const textToSend = questionText || q;
    if (!textToSend.trim() || !project || loadingAsk) return;

    setQ("");
    setMsgs((m) => [...m, { r: "u", t: textToSend }]);
    setLoadingAsk(true);

    const effLevel = overrideLevel !== null ? overrideLevel : pref.knowledge_level;

    try {
      const d = await api("/chat/ask", {
        method: "POST",
        body: JSON.stringify({
          project_id: project.id,
          question: textToSend,
          selected_code: selectedCode,
          knowledge_level: effLevel,
          language: pref.language,
          format: pref.format,
        }),
      });
      setMsgs((m) => [...m, { r: "a", t: d.answer }]);
    } catch (err) {
      setMsgs((m) => [...m, { r: "a", t: "⚠️ Error communicating with AI Tutor: " + err.message }]);
    } finally {
      setLoadingAsk(false);
    }
  }

  return (
    <>
      <header>
        <b>
          <Sparkles color="#8b7cff" /> CodeMate AI
        </b>

        {/* 3-Step Wizard Navigation */}
        <div className="stepper">
          <div
            className={`step-item ${step === "upload" ? "active" : project ? "done" : ""}`}
            onClick={() => setStep("upload")}
          >
            <span className="step-num">{project ? "✓" : "1"}</span>
            <span>Upload</span>
          </div>

          <span className="step-sep">›</span>

          <div
            className={`step-item ${step === "knowledge" ? "active" : msgs.length > 0 ? "done" : ""}`}
            onClick={() => project && setStep("knowledge")}
            style={{ cursor: project ? "pointer" : "not-allowed", opacity: project ? 1 : 0.5 }}
          >
            <span className="step-num">2</span>
            <span>Knowledge Level</span>
          </div>

          <span className="step-sep">›</span>

          <div
            className={`step-item ${step === "tutor" ? "active" : ""}`}
            onClick={() => project && setStep("tutor")}
            style={{ cursor: project ? "pointer" : "not-allowed", opacity: project ? 1 : 0.5 }}
          >
            <span className="step-num">3</span>
            <span>AI Tutor</span>
          </div>
        </div>

        <nav>
          <button className="secondary" onClick={() => setDark(!dark)}>
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button
            className="secondary"
            onClick={() => {
              localStorage.removeItem("cm_token");
              localStorage.removeItem("cm_user_name");
              location.reload();
            }}
          >
            Logout
          </button>
        </nav>
      </header>

      {/* STEP 1: UPLOAD PAGE (ONLY upload shows here) */}
      {step === "upload" && (
        <main className="wizard">
          <div className="page-head">
            <span className="badge-pill">Step 1 of 3 · 1st & 2nd Year Friendly</span>
            <h1>Upload Your Learning Material</h1>
            <p>
              Upload your code files, ZIP projects, PDFs, or Word documents. We will analyze the language and prepare your AI Tutor.
            </p>
          </div>

          <div className="upload-area">
            <div className="upload-dropzone">
              <Upload size={48} />
              <h3>Upload your PDF or Code file</h3>
              <p>.pdf .c .cpp .java .py .html .css .js .jsx .cs .docx .zip</p>

              {/* Hidden file input opened ONLY by the Upload Files button */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".py,.java,.c,.cpp,.h,.cs,.js,.jsx,.html,.css,.txt,.pdf,.docx,.zip"
                onChange={handleFileUpload}
                disabled={uploading}
                style={{ display: "none" }}
              />

              {!uploading ? (
                <button
                  type="button"
                  className="upload-main-btn"
                  onClick={() => fileInputRef.current && fileInputRef.current.click()}
                >
                  <Upload size={18} />
                  Upload Files
                </button>
              ) : (
                <div className="upload-progress-card">
                  <div className="upload-progress-header">
                    <span>{uploadStatusText}</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="upload-progress-track">
                    <div
                      className="upload-progress-fill"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="upload-status-hint">
                    Fast processing in progress... Auto-advancing to Knowledge Level in seconds!
                  </p>
                </div>
              )}
            </div>

            {uploadSuccess && project && (
              <div className="upload-success-card">
                <div className="upload-success-info">
                  <CheckCircle2 size={28} />
                  <div>
                    <h4>{project.original_name} uploaded successfully!</h4>
                    <p>
                      Detected technology: <strong>{availableTechs.join(", ")}</strong> · {project.file_count}{" "}
                      {project.kind === "pdf" ? "pages" : "files"} · {project.line_count} lines ready.
                    </p>
                  </div>
                </div>

                <div className="upload-actions">
                  <button onClick={() => setStep("knowledge")}>
                    Next: Choose Knowledge Level <ArrowRight size={18} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {/* STEP 2: KNOWLEDGE LEVEL PAGE (ONLY detected languages show here) */}
      {step === "knowledge" && project && (
        <main className="wizard">
          <div className="page-head">
            <span className="badge-pill">Step 2 of 3 · Custom Learning Depth</span>
            <h1>Set Your Knowledge Level</h1>
            <p>
              Explanation depth for <strong>{project.original_name}</strong>. Choose your current familiarity and preferred tutoring format.
            </p>
          </div>

          <div className="knowledge-container card">
            {/* Detected Languages ONLY */}
            <div className="detected-lang-box">
              <span className="section-label">Detected Technology from Upload</span>
              <div className="lang-grid">
                {availableTechs.map((t) => (
                  <div
                    key={t}
                    className={`lang-chip ${tech === t ? "active" : ""}`}
                    onClick={() => setTech(t)}
                  >
                    <Code2 size={20} />
                    <span>{t}</span>
                    <span style={{ fontSize: 13, color: "#afa5ff" }}>
                      ({prefs[t]?.knowledge_level || 20}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Explanation Depth Presets */}
            <div>
              <span className="section-label">Explanation Depth ({tech})</span>
              <div className="level-presets">
                <button
                  type="button"
                  className={`preset-btn ${pref.knowledge_level <= 25 ? "active" : ""}`}
                  onClick={() => handleLevelChange(20)}
                >
                  <b>🟢 1st-Year Student (20%)</b>
                  <span>Simple terms, syntax & basic block logic</span>
                </button>

                <button
                  type="button"
                  className={`preset-btn ${pref.knowledge_level > 25 && pref.knowledge_level <= 60 ? "active" : ""}`}
                  onClick={() => handleLevelChange(50)}
                >
                  <b>🟡 Intermediate (50%)</b>
                  <span>Standard technical explanations & logic</span>
                </button>

                <button
                  type="button"
                  className={`preset-btn ${pref.knowledge_level > 60 ? "active" : ""}`}
                  onClick={() => handleLevelChange(80)}
                >
                  <b>🔵 Advanced (80%)</b>
                  <span>Deep dive into memory & architecture</span>
                </button>
              </div>

              {/* Range Slider */}
              <input
                className="range"
                type="range"
                min="5"
                max="100"
                step="5"
                value={pref.knowledge_level}
                onChange={(e) => handleLevelChange(e.target.value)}
              />
              <div className="rangeinfo">
                <span>5% (Extremely Simple)</span>
                <strong style={{ color: "#afa5ff" }}>Current: {pref.knowledge_level}%</strong>
                <span>100% (Deep Technical)</span>
              </div>
            </div>

            {/* Explanation Format Preference */}
            <div className="form-group">
              <span className="section-label">Explanation Format Preference</span>
              <select
                className="select-styled"
                value={pref.format}
                onChange={(e) => handleFormatChange(e.target.value)}
              >
                {FMT.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Language Preference */}
            <div className="form-group">
              <span className="section-label">Explanation Language</span>
              <select
                className="select-styled"
                value={pref.language}
                onChange={(e) => handleLanguageChange(e.target.value)}
              >
                {LANG.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>

            {/* Navigation Buttons */}
            <div className="step-buttons">
              <button className="secondary" onClick={() => setStep("upload")}>
                <ArrowLeft size={16} /> Back to Upload
              </button>

              <button onClick={() => setStep("tutor")}>
                Proceed to AI Tutor <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </main>
      )}

      {/* STEP 3: AI TUTOR PAGE */}
      {step === "tutor" && project && (
        <main className="wizard" style={{ maxWidth: 1300, padding: "20px 20px 40px" }}>
          <div className="tutor-layout">
            {/* Left Sidebar: Document & Pages */}
            <div className="doc-sidebar">
              <div className="doc-sidebar-head">
                <h3>{project.original_name}</h3>
                <p>
                  {tech} · {project.file_count} {project.kind === "pdf" ? "pages" : "files"} · {project.line_count} lines
                </p>
              </div>

              <div className="doc-file-list">
                {files.map((f) => (
                  <button
                    key={f.id}
                    className="file-item"
                    onClick={() => inspectFile(f)}
                    title="Click to view file content"
                  >
                    <FileText size={16} color="#8b7cff" />
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {f.path}
                    </span>
                    <small>{f.language}</small>
                  </button>
                ))}
              </div>
            </div>

            {/* Right Main Area: AI Tutor Chat */}
            <div className="chat-pane">
              <div className="chat-header">
                <div className="chat-header-info">
                  <b>AI Tutor</b>
                  <span>
                    {tech} · {pref.knowledge_level}% Level
                  </span>

                  <div className="chat-level-toggles">
                    <button
                      type="button"
                      className={`chat-level-pill ${pref.knowledge_level <= 25 ? "active" : ""}`}
                      onClick={() => handleLevelChange(20)}
                      title="Set to 20% - 1st Year Syntax & Basics"
                    >
                      🟢 20%
                    </button>
                    <button
                      type="button"
                      className={`chat-level-pill ${pref.knowledge_level > 25 && pref.knowledge_level <= 60 ? "active" : ""}`}
                      onClick={() => handleLevelChange(50)}
                      title="Set to 50% - Intermediate Logic & Flow"
                    >
                      🟡 50%
                    </button>
                    <button
                      type="button"
                      className={`chat-level-pill ${pref.knowledge_level > 60 ? "active" : ""}`}
                      onClick={() => handleLevelChange(80)}
                      title="Set to 80% - Advanced Systems & Memory"
                    >
                      🔵 80%
                    </button>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="secondary"
                    style={{ padding: "6px 12px", fontSize: 12 }}
                    onClick={() => setStep("knowledge")}
                  >
                    <Sliders size={14} /> Full Settings
                  </button>
                  <button
                    className="secondary"
                    style={{ padding: "6px 12px", fontSize: 12 }}
                    onClick={() => setStep("upload")}
                  >
                    <Upload size={14} /> New Upload
                  </button>
                </div>
              </div>

              <div className="messages">
                {msgs.length === 0 && (
                  <div className="tutor-welcome">
                    <h2>
                      <Sparkles size={20} /> Welcome to your {tech} AI Tutor!
                    </h2>
                    <p>
                      I am set up for your <strong>{pref.knowledge_level}% (1st-year student)</strong> level.
                      <br />
                      • <strong>Code Questions:</strong> I explain the <strong>syntax</strong> and break down the code <strong>block by block</strong>.
                      <br />
                      • <strong>Theory Questions:</strong> I explain in{" "}
                      <strong>
                        {pref.format === "points"
                          ? "point-by-point bullet format"
                          : pref.format === "paragraph"
                          ? "para-by-para explanations"
                          : "structured points & paragraphs"}
                      </strong>
                      .
                    </p>

                    <div className="suggestion-pills">
                      <div
                        className="suggestion-pill"
                        onClick={() => askQuestion("Explain the code block by block with structure and syntax")}
                      >
                        <Code2 size={16} color="#8b7cff" />
                        <span>Explain the code block by block with structure and syntax</span>
                      </div>

                      <div
                        className="suggestion-pill"
                        onClick={() => askQuestion("Explain the basic program structure and syntax for a 1st-year student")}
                      >
                        <BookOpen size={16} color="#8b7cff" />
                        <span>Explain the basic program structure and syntax for a 1st-year student</span>
                      </div>

                      <div
                        className="suggestion-pill"
                        onClick={() => askQuestion("What are the inputs, calculations, and outputs step by step?")}
                      >
                        <HelpCircle size={16} color="#8b7cff" />
                        <span>What are the inputs, calculations, and outputs step by step?</span>
                      </div>

                      <div
                        className="suggestion-pill"
                        onClick={() => askQuestion("Explain the theoretical concepts and principles in points")}
                      >
                        <Sparkles size={16} color="#8b7cff" />
                        <span>Explain the theoretical concepts and principles in points</span>
                      </div>
                    </div>
                  </div>
                )}

                {msgs.map((m, i) => (
                  <div key={i} className={`msg-row ${m.r === "u" ? "user" : "ai"}`}>
                    <div className={m.r === "u" ? "user" : "ai"}>
                      {m.r === "u" ? m.t : <FormattedMessage text={m.t} />}
                    </div>
                  </div>
                ))}

                {loadingAsk && (
                  <div className="msg-row ai">
                    <div className="ai" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Sparkles size={16} className="animate-spin" color="#8b7cff" />
                      <span>CodeMate Tutor is preparing your 1st-year explanation...</span>
                    </div>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>

              <div className="composer">
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && askQuestion()}
                  placeholder={`Ask a code or theory question about ${project.original_name}...`}
                />
                <button onClick={() => askQuestion()} disabled={loadingAsk || !q.trim()}>
                  <Send size={18} />
                </button>
              </div>
            </div>
          </div>
        </main>
      )}

      {/* Modal to view individual page/file content */}
      {viewingFile && (
        <div className="modal">
          <div className="codebox">
            <div>
              <b>{viewingFile.path}</b>
              <button className="secondary" onClick={() => setViewingFile(null)}>
                Close
              </button>
            </div>

            <div className="codebox-content">
              {loadingFile ? "Loading content..." : fileContent}
            </div>

            <div className="codebox-footer">
              <button
                onClick={() => {
                  const targetCode = fileContent;
                  const targetPath = viewingFile.path;
                  setViewingFile(null);
                  if (step !== "tutor") setStep("tutor");
                  askQuestion(`Explain the code and syntax on ${targetPath} block by block`, targetCode);
                }}
              >
                Ask AI Tutor to Explain This Block by Block
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Root() {
  const [token, setToken] = useState(localStorage.getItem("cm_token"));
  return token ? <App /> : <Login done={() => setToken(localStorage.getItem("cm_token"))} />;
}

createRoot(document.getElementById("root")).render(<Root />);
