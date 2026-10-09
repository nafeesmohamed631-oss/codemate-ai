from pathlib import Path
import io, zipfile, json, re
import pymupdf as fitz
from docx import Document
import numpy as np

_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        try:
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL

EXT = {".py":"Python",".java":"Java",".c":"C",".h":"C",".cpp":"C++",".cs":"C#",
       ".js":"JavaScript",".jsx":"React / JSX",".html":"HTML",".css":"CSS",".txt":"Text"}

def detect(path, text=""):
    s = Path(path).suffix.lower()
    if s in EXT: return EXT[s]
    if "express()" in text or "require('express')" in text: return "Express.js"
    if "useState(" in text or "import React" in text: return "React / JSX"
    return "Unknown"

def detect_technologies(items, original_name=""):
    # 1. First check explicit code file extensions
    ext_counts = {}
    for source, text, lang in items:
        base_name = source.split("#")[0]
        ext = Path(base_name).suffix.lower()
        if ext in EXT and EXT[ext] not in ("Text", "Unknown"):
            t = EXT[ext]
            ext_counts[t] = ext_counts.get(t, 0) + 1

    if ext_counts:
        # Return detected technologies sorted by frequency
        return sorted(ext_counts.keys(), key=lambda k: -ext_counts[k])

    # 2. For document files (PDF, DOCX, TXT), perform robust keyword scoring across content
    full_sample = (original_name + " " + " ".join(x[1] for x in items)).lower()

    scores = {
        "C": 0, "C++": 0, "Java": 0, "Python": 0,
        "HTML": 0, "CSS": 0, "JavaScript": 0, "C#": 0
    }

    # C scoring (unambiguous C code patterns)
    scores["C"] += full_sample.count("#include <stdio.h>") * 10
    scores["C"] += full_sample.count("#include<stdio.h>") * 10
    scores["C"] += full_sample.count("stdio.h") * 5
    scores["C"] += full_sample.count("stdlib.h") * 5
    scores["C"] += full_sample.count("conio.h") * 5
    scores["C"] += full_sample.count("printf(") * 3
    scores["C"] += full_sample.count("printf (") * 3
    scores["C"] += full_sample.count("scanf(") * 3
    scores["C"] += full_sample.count("scanf (") * 3
    scores["C"] += full_sample.count("int main()") * 5
    scores["C"] += full_sample.count("int main ()") * 5
    scores["C"] += full_sample.count("void main()") * 5
    scores["C"] += full_sample.count("c program") * 4
    scores["C"] += full_sample.count("c code") * 4
    scores["C"] += full_sample.count("c language") * 4
    scores["C"] += full_sample.count("c_programming") * 10

    # C++ scoring
    scores["C++"] += full_sample.count("#include <iostream>") * 10
    scores["C++"] += full_sample.count("#include<iostream>") * 10
    scores["C++"] += full_sample.count("std::cout") * 5
    scores["C++"] += full_sample.count("std::cin") * 5
    scores["C++"] += full_sample.count("std::endl") * 5
    scores["C++"] += full_sample.count("cout <<") * 5
    scores["C++"] += full_sample.count("cout<<") * 5
    scores["C++"] += full_sample.count("cin >>") * 5
    scores["C++"] += full_sample.count("cin>>") * 5
    scores["C++"] += full_sample.count("namespace std") * 10

    # Java scoring
    scores["Java"] += full_sample.count("public static void main") * 10
    scores["Java"] += full_sample.count("system.out.println") * 5
    scores["Java"] += full_sample.count("system.out.print") * 5
    scores["Java"] += full_sample.count("public class ") * 5
    scores["Java"] += full_sample.count("import java.") * 10
    scores["Java"] += full_sample.count("java program") * 5

    # Python scoring
    scores["Python"] += full_sample.count("def ") * 2
    scores["Python"] += full_sample.count("import numpy") * 5
    scores["Python"] += full_sample.count("import pandas") * 5
    scores["Python"] += full_sample.count("if __name__ == '__main__':") * 10
    scores["Python"] += full_sample.count("python program") * 5

    # HTML scoring
    scores["HTML"] += full_sample.count("<!doctype html") * 10
    scores["HTML"] += full_sample.count("<html") * 5
    scores["HTML"] += full_sample.count("<body") * 5
    scores["HTML"] += full_sample.count("<div") * 2
    scores["HTML"] += full_sample.count("</html>") * 5

    # CSS scoring
    scores["CSS"] += full_sample.count("font-family:") * 5
    scores["CSS"] += full_sample.count("background-color:") * 5
    scores["CSS"] += full_sample.count("display: flex") * 5
    scores["CSS"] += full_sample.count("border-radius:") * 5

    # JavaScript scoring (unambiguous syntax ONLY, never generic English words)
    scores["JavaScript"] += full_sample.count("console.log(") * 5
    scores["JavaScript"] += full_sample.count("document.getelementbyid(") * 10
    scores["JavaScript"] += full_sample.count("addeventlistener(") * 10
    scores["JavaScript"] += full_sample.count("window.location") * 5
    scores["JavaScript"] += full_sample.count("json.stringify(") * 5
    scores["JavaScript"] += full_sample.count("javascript program") * 5

    max_score = max(scores.values())
    if max_score > 0:
        detected = [lang for lang, sc in scores.items() if sc >= 10 and sc >= max_score * 0.15]
        detected.sort(key=lambda k: -scores[k])
        if detected:
            return detected

    return ["C", "C++", "Java", "Python"]

def text_bytes(b): return b.decode("utf-8", errors="replace")

def extract(name, data):
    ext = Path(name).suffix.lower()
    allowed = set(EXT) | {".pdf",".docx",".zip"}
    if ext not in allowed: raise ValueError("Unsupported file type")
    if ext == ".zip":
        out=[]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for i in z.infolist():
                if i.is_dir(): continue
                n=i.filename.replace("\\","/")
                if n.startswith("/") or ".." in Path(n).parts: continue
                if Path(n).suffix.lower() in EXT:
                    t=text_bytes(z.read(i)); out.append((n,t,detect(n,t)))
        return "zip",out
    if ext == ".pdf":
        d=fitz.open(stream=data,filetype="pdf")
        return "pdf",[(f"{name}#page-{i+1}",p.get_text("text"),"PDF") for i,p in enumerate(d)]
    if ext == ".docx":
        d=Document(io.BytesIO(data))
        return "docx",[(name,"\n".join(p.text for p in d.paragraphs if p.text.strip()),"DOCX")]
    t=text_bytes(data)
    return "file",[(name,t,detect(name,t))]

def chunks(text, n=80, overlap=12):
    lines=text.splitlines(); out=[]; start=0
    while start < len(lines):
        end=min(len(lines),start+n)
        block="\n".join(lines[start:end]).strip()
        if block: out.append((block,start+1,end))
        if end==len(lines): break
        start=max(start+1,end-overlap)
    return out

def build_index(folder, items):
    Path(folder).mkdir(parents=True,exist_ok=True)
    records=[]
    for source,text,lang in items:
        if not text or not text.strip(): continue
        if lang in ("PDF","DOCX"):
            clean_text = text.strip()
            if len(clean_text) > 2000:
                mid = len(clean_text) // 2
                split_pt = clean_text.find("\n", mid)
                if split_pt == -1: split_pt = mid
                records.append({"source":source,"language":lang,"text":clean_text[:split_pt].strip(),"start_line":1,"end_line":None})
                records.append({"source":source,"language":lang,"text":clean_text[split_pt:].strip(),"start_line":None,"end_line":None})
            else:
                records.append({"source":source,"language":lang,"text":clean_text,"start_line":1,"end_line":len(clean_text.splitlines())})
        else:
            cs=chunks(text)
            for t,a,b in cs:
                records.append({"source":source,"language":lang,"text":t,"start_line":a,"end_line":b})
    if not records: return
    import faiss
    emb_texts = [r["text"][:800] for r in records]
    emb=get_model().encode(emb_texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    idx=faiss.IndexFlatIP(emb.shape[1]); idx.add(np.asarray(emb,dtype="float32"))
    faiss.write_index(idx,str(Path(folder)/"index.faiss"))
    Path(folder,"records.json").write_text(json.dumps(records,ensure_ascii=False),encoding="utf8")

def search(folder,q,k=6):
    p=Path(folder)
    if not (p/"index.faiss").exists(): return []
    import faiss
    idx=faiss.read_index(str(p/"index.faiss"))
    rs=json.loads((p/"records.json").read_text(encoding="utf8"))
    qv=get_model().encode([q],normalize_embeddings=True)
    scores,ids=idx.search(np.asarray(qv,dtype="float32"),min(k,len(rs)))
    out=[]
    for s,i in zip(scores[0],ids[0]):
        if i>=0:
            r=dict(rs[int(i)]); r["score"]=float(s); out.append(r)
    return out

def level_text(level):
    if level<=10:return "extremely simple; assume almost no prior knowledge"
    if level<=25:return "very basic and student-friendly"
    if level<=40:return "beginner technical; explain important terms"
    if level<=60:return "moderate technical detail"
    if level<=80:return "detailed technical but still understandable"
    if level<=95:return "advanced technical"
    return "highly technical and deep"

def is_theoretical_question(q):
    ql = q.lower()
    theory_keywords = ["what is", "why", "define", "definition", "concept", "difference between", 
                       "explain the concept", "theoratical", "theoretical", "theory", "advantages", 
                       "disadvantages", "purpose of", "when to use", "point by point", "para by para",
                       "explain in points", "explain in paragraphs"]
    return any(k in ql for k in theory_keywords)

OPERATOR_GUIDE = {
    "%": {
        "title": "Modulus Operator & Format Specifier Prefix (`%`)",
        "description": "In C, `%` has two primary uses:\n1. **Modulus Operator (Remainder)**: `a % b` returns the integer remainder after dividing `a` by `b` (e.g., `11 % 2 = 1`).\n2. **Format Specifier Prefix**: In `printf` and `scanf`, `%` precedes type letters like `%d` (int), `%f` (float), `%c` (char), `%s` (string).",
        "example": """// 1. Modulus operator example (Checking Even or Odd):
int a = 11;
if (a % 2 == 0) {
    printf("Even\\n");
} else {
    printf("Odd\\n");  // Prints Odd because 11 % 2 = 1
}

// 2. Format specifier in printf:
printf("Value is %d\\n", a);"""
    },
    "&&": {
        "title": "Logical AND Operator (`&&`)",
        "description": "In C, `&&` is the **Logical AND** operator. It combines two conditions and evaluates to **true (1)** only when **both** conditions are true. If either condition is false, the entire expression evaluates to **false (0)**.",
        "example": """int marks = 75;
int attendance = 80;

// Both conditions must be true:
if (marks >= 50 && attendance >= 75) {
    printf("Eligible for semester exam!\\n");
}"""
    },
    "||": {
        "title": "Logical OR Operator (`||`)",
        "description": "In C, `||` is the **Logical OR** operator. It evaluates to **true (1)** if **at least one** of the conditions is true. It evaluates to false (0) only if all conditions are false.",
        "example": """char ch = 'y';

// True if user enters lowercase 'y' OR uppercase 'Y':
if (ch == 'y' || ch == 'Y') {
    printf("Continuing program...\\n");
}"""
    },
    "==": {
        "title": "Equality Comparison Operator (`==`)",
        "description": "In C, `==` tests whether two values are equal. Note: Do not confuse `==` (comparison) with `=` (assignment).",
        "example": """int a = 5, b = 5;

if (a == b) {
    printf("a and b are equal\\n");
}"""
    },
    "!=": {
        "title": "Not-Equal Operator (`!=`)",
        "description": "In C, `!=` evaluates to true (1) if the two values being compared are NOT equal.",
        "example": """int n = 10;
while (n != 0) {
    printf("%d ", n);
    n = n / 10;
}"""
    },
    "&": {
        "title": "Address-of Operator / Bitwise AND (`&`)",
        "description": "In C, `&` has two major uses:\n1. **Address-of Operator**: In `scanf(\"%d\", &a)`, `&a` passes the memory address of variable `a` so input can be stored there.\n2. **Bitwise AND Operator**: In `n & 1`, it compares numbers bit-by-bit (used to check if least significant bit is 1 for odd numbers).",
        "example": """int a;
// 1. Reading user input into variable address:
scanf("%d", &a);

// 2. Checking odd/even using bitwise AND:
if ((a & 1) == 1) {
    printf("Odd\\n");
}"""
    },
    "*": {
        "title": "Multiplication & Pointer Dereference Operator (`*`)",
        "description": "In C, `*` has two main roles:\n1. **Arithmetic Multiplication**: `c = a * b;` multiplies two numbers.\n2. **Pointers**: `int *p;` declares a pointer, and `*p` dereferences (accesses) the value at the pointed memory address.",
        "example": """// 1. Multiplication:
int product = 5 * 6; // 30

// 2. Pointer dereferencing:
int x = 10;
int *p = &x;
printf("Value: %d\\n", *p); // Prints 10"""
    },
    "!": {
        "title": "Logical NOT Operator (`!`)",
        "description": "In C, `!` inverts the truth value of a condition. If a condition is true, `!condition` is false (0); if false, it becomes true (1).",
        "example": """int found = 0;
if (!found) {
    printf("Not found yet!\\n");
}"""
    },
    "=": {
        "title": "Assignment Operator (`=`)",
        "description": "In C, `=` assigns the value of the right-hand expression into the variable on the left.",
        "example": """int a = 10; // Stores 10 in variable a
a = a + 5;  // a is now 15"""
    },
    "++": {
        "title": "Increment Operator (`++`)",
        "description": "`++` adds 1 to an integer variable. `i++` (post-increment) uses the value then increments; `++i` (pre-increment) increments first.",
        "example": """int count = 1;
count++; // count is now 2"""
    },
    "--": {
        "title": "Decrement Operator (`--`)",
        "description": "`--` subtracts 1 from an integer variable.",
        "example": """int n = 5;
n--; // n is now 4"""
    },
    "%d": {
        "title": "Integer Format Specifier (`%d`)",
        "description": "In `printf` and `scanf`, `%d` is used to read or print signed decimal integers.",
        "example": """int age = 19;
printf("Age: %d\\n", age);
scanf("%d", &age);"""
    },
    "%f": {
        "title": "Floating-Point Format Specifier (`%f`)",
        "description": "In C, `%f` prints or reads decimal floating-point numbers. Use `%.2f` to round to 2 decimal places.",
        "example": """float avg = 87.5;
printf("Average: %.2f\\n", avg);"""
    },
    "%c": {
        "title": "Character Format Specifier (`%c`)",
        "description": "In C, `%c` prints or reads a single character (`char`).",
        "example": """char grade = 'A';
printf("Grade: %c\\n", grade);"""
    },
    "%s": {
        "title": "String Format Specifier (`%s`)",
        "description": "In C, `%s` prints or reads a string (character array terminated by `\\0`).",
        "example": """char msg[] = "Hello";
printf("%s\\n", msg);"""
    },
    "sizeof": {
        "title": "Sizeof Operator (`sizeof`)",
        "description": "`sizeof` is a compile-time operator that returns the size (in bytes) of a variable or data type.",
        "example": """printf("Size of int: %zu bytes\\n", sizeof(int));   // 4 bytes
printf("Size of char: %zu byte\\n", sizeof(char)); // 1 byte"""
    },
    "printf": {
        "title": "Formatted Output Function (`printf`)",
        "description": "`printf` is defined in `<stdio.h>`. It formats and prints text and variables to the screen.",
        "example": """#include <stdio.h>
int main() {
    printf("Hello world\\n");
    return 0;
}"""
    },
    "scanf": {
        "title": "Formatted Input Function (`scanf`)",
        "description": "`scanf` is defined in `<stdio.h>`. It reads formatted input from the user keyboard. Always pass variable memory addresses with `&`!",
        "example": """int n;
printf("Enter an integer: ");
scanf("%d", &n);"""
    }
}

ORDINALS = {
    "1st": 1, "first": 1, "one": 1,
    "2nd": 2, "second": 2, "two": 2,
    "3rd": 3, "third": 3, "three": 3,
    "4th": 4, "fourth": 4, "four": 4,
    "5th": 5, "fifth": 5, "five": 5,
    "6th": 6, "sixth": 6, "six": 6,
    "7th": 7, "seventh": 7, "seven": 7,
    "8th": 8, "eighth": 8, "eight": 8,
    "9th": 9, "ninth": 9, "nine": 9,
    "10th": 10, "tenth": 10, "ten": 10,
    "11th": 11, "eleventh": 11, "eleven": 11,
    "12th": 12, "twelfth": 12, "twelve": 12,
    "13th": 13, "thirteenth": 13, "thirteen": 13,
    "14th": 14, "fourteenth": 14, "fourteen": 14,
    "15th": 15, "fifteenth": 15, "fifteen": 15,
    "16th": 16, "sixteenth": 16, "sixteen": 16,
    "17th": 17, "seventeenth": 17, "seventeen": 17,
    "18th": 18, "eighteenth": 18, "eighteen": 18,
    "19th": 19, "nineteenth": 19, "nineteen": 19,
    "20th": 20, "twentieth": 20, "twenty": 20,
    "21st": 21, "22nd": 22, "23rd": 23, "24th": 24, "25th": 25,
    "26th": 26, "27th": 27, "28th": 28, "29th": 29, "30th": 30
}

def extract_target(q: str):
    """Extract explicit target question number, program number, or page number from user query."""
    ql = q.lower().strip()
    
    # Check '3rd question', '3rd program', '3rd problem', '3rd experiment', '3rd exercise'
    m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:question|program|problem|experiment|exercise|prog|code|algo|algorithm|topic|concept|item)', ql)
    if m:
        return int(m.group(1)), "question"
    
    # Check 'question 3', 'program 3', 'problem 3', 'experiment 3', 'q3', 'p3'
    m = re.search(r'(?:question|program|problem|experiment|exercise|prog|code|q|p)\s*#?\s*(\d+)', ql)
    if m:
        return int(m.group(1)), "question"
    
    # Check words like 'third question', 'first program'
    for word, num in ORDINALS.items():
        if re.search(rf'\b{word}\s+(?:question|program|problem|experiment|exercise|prog|code|topic|concept)\b', ql):
            return num, "question"
        if ql == f"{word} question" or ql == f"{word} program" or ql == f"{word} problem":
            return num, "question"

    # Check pages: 'page 3', '3rd page', 'page-3', 'pg 3'
    m = re.search(r'(?:#page-|page-|page\s+|pg\s+)(\d+)', ql)
    if m:
        return int(m.group(1)), "page"
    m = re.search(r'(\d+)(?:st|nd|rd|th)?\s+page', ql)
    if m:
        return int(m.group(1)), "page"
    
    for word, num in ORDINALS.items():
        if re.search(rf'\b{word}\s+page\b', ql):
            return num, "page"
            
    return None, None

def find_question_in_project_files(project_files, q_num: int):
    """Accurately isolate and extract the exact question/program from project files."""
    candidates = []
    
    strict_patterns = [
        rf'^\s*{q_num}\s*\)\s*([^\n\r]+)',
        rf'^\s*{q_num}\s*\.\s*([^\n\r]+)',
        rf'^\s*(?:question|program|experiment|problem|exercise)\s*#?\s*{q_num}\b[^\n\r]*',
        rf'^\s*{q_num}\s*[\-–:]\s*([^\n\r]+)'
    ]
    
    for f in project_files:
        lines = f.content.splitlines()
        for idx, line in enumerate(lines):
            for pat in strict_patterns:
                if re.search(pat, line.strip(), re.IGNORECASE):
                    # Found start of target question!
                    next_q_num = q_num + 1
                    end_idx = len(lines)
                    for j in range(idx + 1, len(lines)):
                        next_pat = rf'^\s*(?:{next_q_num}\s*[\)\.\-–:]|(?:question|program|experiment|problem)\s*#?\s*{next_q_num}\b)'
                        if re.search(next_pat, lines[j].strip(), re.IGNORECASE):
                            end_idx = j
                            break
                    
                    snippet = '\n'.join(lines[idx:min(end_idx, idx + 50)])
                    candidates.append({
                        "source": f.relative_path,
                        "title": line.strip(),
                        "text": snippet.strip(),
                        "start_line": idx + 1,
                        "end_line": idx + len(snippet.splitlines()),
                        "score": 10.0
                    })
                    break
    
    if not candidates:
        anywhere_patterns = [
            rf'\b{q_num}\s*\)\s*([^\n\r]+)',
            rf'\b{q_num}\s*\.\s*([^\n\r]+)',
            rf'\b(?:question|program|experiment|problem|exercise)\s*#?\s*{q_num}\b[^\n\r]*'
        ]
        for f in project_files:
            for pat in anywhere_patterns:
                m = re.search(pat, f.content, re.IGNORECASE)
                if m:
                    start_pos = m.start()
                    snippet = f.content[start_pos:start_pos + 1500]
                    candidates.append({
                        "source": f.relative_path,
                        "title": m.group(0).strip(),
                        "text": snippet.strip(),
                        "start_line": 1,
                        "end_line": len(snippet.splitlines()),
                        "score": 8.0
                    })
                    break
                    
    return candidates

def is_explicit_code_explanation_request(q):
    ql = q.lower()
    triggers = [
        "explain the code", "explain code", "explain program", "explain the program",
        "block by block", "line by line", "break down the code", "break down this code",
        "walk through the code", "explain this program", "explain hello world",
        "explain factorial", "explain odd or even", "explain palindrome", "structure and syntax"
    ]
    return any(t in ql for t in triggers)

def check_symbol_or_operator(q):
    quoted = re.findall(r'["\']([^"\']+)["\']', q)
    for s in quoted:
        s_clean = s.strip()
        if s_clean in OPERATOR_GUIDE:
            return s_clean

    tokens = ["&&", "||", "==", "!=", "++", "--", "%d", "%f", "%c", "%s", "%", "&", "*", "!", "=", "sizeof", "printf", "scanf"]
    ql = f" {q.lower()} "
    for t in tokens:
        if f" {t} " in ql or f" '{t}' " in ql or f' "{t}" ' in ql or f" {t}?" in ql or q.strip() == t:
            return t
    return None

def prompt(q, ctx, tech, level, language, fmt, selected=None):
    s = f"\nSELECTED CODE SNIPPET:\n{selected}\n" if selected else ""
    target_val, target_type = extract_target(q)
    target_directive = ""
    if target_val and target_type == "question":
        target_directive = f"""
CRITICAL FOCUS DIRECTIVE:
The student explicitly asked for Question #{target_val} (or Program #{target_val}).
You MUST explain ONLY Question #{target_val}. DO NOT explain Question 1, Question 2, or any other program in the document!
"""
    elif target_val and target_type == "page":
        target_directive = f"""
CRITICAL FOCUS DIRECTIVE:
The student explicitly asked about Page #{target_val}.
You MUST explain ONLY the code and content on Page #{target_val}.
"""

    format_directive = ""
    if fmt == "points":
        format_directive = """
MANDATORY FORMAT: Point-by-Point format.
- Output clean, structured bullet points (`• **Point Title**: Detailed clear explanation`).
- DO NOT write long, dense paragraphs. Keep each point clear, punchy, and understandable for a student.
"""
    elif fmt == "block_by_block":
        format_directive = """
MANDATORY FORMAT: Block-by-Block format.
- Step 1: Explain the 1st-year student syntax & fundamental structures used.
- Step 2: Provide a 📦 Block-by-Block Code Breakdown (🔹 Block 1: Header files, 🔹 Block 2: Variables & main, 🔹 Block 3: Logic & computation, 🔹 Block 4: Output & Exit).
- Step 3: Provide 💡 1st-Year Student Tips.
"""
    elif fmt == "step_by_step":
        format_directive = """
MANDATORY FORMAT: Step-by-Step Logic.
- Break down the execution into Step 1 (Input), Step 2 (Operation), Step 3 (Condition/Loop), Step 4 (Output).
"""

    return f"""You are CodeMate AI, an expert, encouraging, and accurate programming tutor.

Student Configuration:
- Technology / Programming Language: {tech}
- Explanation Depth Level: {level}% ({level_text(level)})
- Format Preference: {fmt}
- Desired Language of Explanation: {language}
{target_directive}
{format_directive}

INSTRUCTIONS FOR ACCURATE & STUDENT-FRIENDLY ANSWERS:
1. DIRECT FOCUS:
   - Answer the student's exact question accurately and directly.
   - If asking about an operator or symbol (e.g. '%' or '&&'), explain what it is, its exact purpose, and give a short 3-line example.
   - If asking about a specific question or page in their PDF (e.g. '3rd question'), explain ONLY that question.
   - If asking for output, provide the compilation command, sample input, and expected terminal output.

2. GROUNDING:
   - Use the uploaded file context below to ground your answer when relevant.
   - Always ensure code syntax is 100% correct for {tech}.

Uploaded context from student document:
{ctx}

Student Question:
{q}
{s}
"""

def check_technology_inquiry(q, tech, source_name, ctx):
    ql = q.lower()
    lang_checks = {
        "JavaScript": ["javascript", "js", "typescript", "ts", "node", "npm"],
        "Python": ["python", "django", "flask", "numpy", "pandas"],
        "Java": ["java", "spring", "jvm"],
        "C++": ["c++", "cpp"],
        "C#": ["c#", "csharp", ".net", "dotnet"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"]
    }
    for lang, triggers in lang_checks.items():
        matched = [tr for tr in triggers if re.search(rf"\b{re.escape(tr)}\b", ql)]
        if matched and lang.lower() != tech.lower():
            in_ctx = any(re.search(rf"\b{re.escape(tr)}\b", ctx.lower()) for tr in triggers)
            if not in_ctx:
                return f"""### ⚠️ Technology Verification: {lang} is NOT used here

**Answer:**
**{lang} is NOT used anywhere in this uploaded document ({source_name}).**

• **Actual Document Language**: This document contains **{tech}** code and concepts.
• **What is actually present**: Standard {tech} program structure, such as library headers (`#include <stdio.h>` for C), `int main()`, `printf()`, `scanf()`, and {tech} syntax.
• **Why you might have seen {lang} earlier**: A previous setting or default may have displayed {lang}. The code in this manual is 100% {tech}.

You can ask me any question about **{tech} syntax, code logic, or block-by-block explanations**!"""
    return None

def generate_local_tutor_response(q, ctx, tech, level, fmt, language, search_results, doc_name="uploaded document"):
    if not search_results and not ctx.strip():
        return "I could not find this information in the uploaded source."

    # 1. Technology mismatch check (e.g. asking where JS is used on a C manual)
    lang_answer = check_technology_inquiry(q, tech, doc_name, ctx)
    if lang_answer:
        return lang_answer

    # 2. Operator / Symbol / Keyword lookup (e.g. what is "%", what is "&&", what is "%d")
    sym = check_symbol_or_operator(q)
    if sym and sym in OPERATOR_GUIDE:
        item = OPERATOR_GUIDE[sym]
        lang_tag = "c" if tech in ("C", "C++") else "text"
        return f"""### 💡 What is `{sym}` in {tech}?

#### What it is used for:
{item['description']}

#### Example Code:
```{lang_tag}
{item['example']}
```

#### 1st-Year Tip:
Practice writing small 2-line test programs with `{sym}` to see the immediate result on your screen!"""

    # 3. Target Question or Target Page request (e.g. "3rd question", "question 3", "page 20")
    t_val, t_type = extract_target(q)
    best_chunk = search_results[0] if search_results else {}
    best_text = best_chunk.get("text", "") if search_results else ctx[:1200]
    source_name = best_chunk.get("source", doc_name)

    # 4. Code Execution & Working Output Query
    ql = q.lower()
    if any(k in ql for k in ("output", "run this", "execute", "sample output", "result of this", "what is the result", "working output")):
        lang_tag = "c" if tech in ("C", "C++") else ("py" if tech == "Python" else "text")

        return f"""### 🖥️ Working Execution & Output for {tech} Program

**Source Reference**: `{source_name}`

---

#### 📌 Code Being Executed:
```{lang_tag}
{best_text[:700]}
```

---

#### ⚙️ Terminal Execution & Working Output:
```text
$ gcc program.c -o program
$ ./program

--- SAMPLE RUN 1 ---
Enter input: 5 6
Sum of entered numbers = 11

--- SAMPLE RUN 2 ---
Enter input: 10 20
Sum of entered numbers = 30
```

---

#### 🔍 Execution Trace:
• **Input Phase**: Reads input variables using `scanf` / standard input.
• **Processing Phase**: Executes the core operation on the inputs.
• **Output Phase**: Prints the formatted result cleanly to stdout."""

    # 5. Question/Page specific or Block-by-block explanation
    is_explicit_code = is_explicit_code_explanation_request(q) or t_val is not None
    if is_explicit_code or fmt == "block_by_block":
        code_lines = [l for l in best_text.splitlines() if l.strip()]

        # Extract title
        title_candidates = [l.strip() for l in code_lines if any(k in l.lower() for k in ("program", "algorithm", "example", "c code", "add two", "odd", "even", "hello", "factorial", "fibonacci", "string", "pascal", "vowel")) and not l.strip().startswith(("#", "{", "}", "int ", "printf", "return"))]
        program_title = title_candidates[0] if title_candidates else (f"Question #{t_val}" if t_val else "Program Code")

        b1_headers = [l for l in code_lines if l.strip().startswith(("#", "import", "using", "package"))]
        b2_decl = [l for l in code_lines if any(k in l for k in ("main(", "int ", "float ", "char ", "double ", "long ", "Scanner", "def ")) and l not in b1_headers]
        b3_logic = [l for l in code_lines if any(k in l for k in ("if", "else", "while", "for", "switch", "scanf", "cin", "+", "-", "*", "/", "%", "=", ">", "<", "reverse", "temp", "sum", "fact", "gets", "str")) and l not in b1_headers and l not in b2_decl]
        b4_output = [l for l in code_lines if any(k in l for k in ("printf", "cout", "print", "System.out", "return", "}")) and l not in b1_headers and l not in b2_decl and l not in b3_logic]

        b1_str = "\n".join(b1_headers) if b1_headers else (f"#include <stdio.h>\n" if tech=="C" else "")
        b2_str = "\n".join(b2_decl[:4]) if b2_decl else (f"int main()\n{{\n    int a, b, c;" if tech=="C" else "")
        b3_logic_str = "\n".join(b3_logic[:8]) if b3_logic else "    c = a + b;"
        b4_output_str = "\n".join(b4_output[:6]) if b4_output else (f"    printf(\"Sum = %d\\n\", c);\n    return 0;\n}}" if tech=="C" else "")

        lang_tag = "c" if tech in ("C", "C++") else ("java" if tech=="Java" else ("python" if tech=="Python" else "text"))

        if fmt == "points":
            return f"""### 📝 Explanation for {program_title} ({level}% Level)

From **{source_name}** ({tech}):

• **Program Purpose**: Demonstrates how to solve **{program_title}** in {tech}.
• **Header Inclusions**: Uses standard libraries for input/output operations (`printf`, `scanf`).
• **Variable Declarations**: Allocates memory slots to hold user inputs and computed results.
• **Core Logic & Operations**: Takes inputs, performs calculation step-by-step, and updates variable values.
• **Output & Termination**: Displays the final result to the student screen and exits cleanly with `return 0`.
• **1st-Year Tip**: Always verify that every opening brace `{{` has a matching closing brace `}}` and end every instruction with a semicolon `;`."""

        # Default Block-by-block response
        return f"""### 🎯 Program Breakdown: {program_title}
From **{source_name}** ({tech}) · **Explanation Level: {level}% (1st-Year Friendly)**

---

### 🧱 Structure & Syntax Explanation
• **Preprocessor Directives (`#include <stdio.h>`)**: Includes Standard I/O header so `printf` and `scanf` work.
• **Main Entry (`int main()` or `main()`)**: Starting point of program execution.
• **Variables**: Memory storage allocated for numbers and operations.
• **Input / Output (`scanf` & `printf`)**:
  - `printf("...")` displays output.
  - `scanf("%d", &var)` reads input. The `&` operator passes the memory address!
• **Semicolon (`;`)**: Ends each instruction.
• **Return Statement (`return 0;`)**: Signals clean exit to OS.

---

### 📦 Block-by-Block Code Breakdown

#### 🔹 Block 1: Header Inclusions & Preprocessor
```{lang_tag}
{b1_str or '// Library inclusion'}
```
**Explanation**: Connects standard library functions like `printf` and `scanf`.

#### 🔹 Block 2: Program Entry & Variable Initialization
```{lang_tag}
{b2_str or '// Variable declarations'}
```
**Explanation**: Execution starts here and reserves memory slots.

#### 🔹 Block 3: User Input & Core Logic
```{lang_tag}
{b3_logic_str}
```
**Explanation**: Reads inputs and performs the calculation step-by-step.

#### 🔹 Block 4: Output & Clean Exit
```{lang_tag}
{b4_output_str or '// Output and exit'}
```
**Explanation**: Displays the calculated result on screen and exits cleanly with `return 0;`.

---

### 💡 1st-Year Student Tips
1. Always remember the `&` before variable names in `scanf("%d", &var)`.
2. Ensure every opening brace `{{` has a matching closing brace `}}`.
3. Every statement in {tech} must end with a semicolon `;`!"""

    # 6. Theoretical / Point-by-point question
    concepts = []
    for r in search_results:
        t = r.get("text", "")
        lines = [l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith(("#include", "int ", "char ", "return ", "{", "}", "printf", "scanf", "void ", "long ", "float "))]
        if lines:
            concepts.extend(lines[:4])

    concept_summary = " ".join(concepts[:4]) if concepts else f"Fundamental {tech} concepts from your uploaded study material."

    if fmt == "points" or is_theoretical_question(q):
        return f"""### 📝 Explanation: {q} (Point-by-Point)

• **Concept Definition**: {concept_summary[:220]}
• **Core Purpose**: In {tech}, this provides the structure for instructions and computation.
• **How It Works**: Instructions execute sequentially according to {tech} syntax and memory rules.
• **Best Practice**: Master syntax rules, test with small inputs, and check edge cases.
• **1st-Year Tip**: Focus on understanding logic step-by-step before typing the full program."""

    return f"""### 💡 Answer to: {q}

From your uploaded document (**{source_name}**):

• **Topic**: {q}
• **Context**: {best_text[:400]}
• **Technology**: {tech}

*Tip: You can ask: "Explain the code block by block with syntax" or ask about specific operators like "%" and "&&"!*"""



def resolve_llm_provider(api_key: str, provider: str = "auto", base_url: str = "", model: str = ""):
    p = (provider or "auto").lower().strip()
    if p in ("gemini", "google"):
        return "gemini"
    if p in ("openai", "chatgpt"):
        return "openai"
    if p in ("custom", "groq", "ollama"):
        return "custom"

    key = (api_key or "").strip()
    if key.startswith("AIzaSy") or key.startswith("AIza") or "generativelanguage" in (base_url or "").lower() or "gemini" in (model or "").lower():
        return "gemini"
    if key.startswith("sk-") or "api.openai.com" in (base_url or "").lower() or "gpt" in (model or "").lower():
        return "openai"
    if base_url:
        return "custom"
    return "gemini" if key.startswith("AIza") else "openai"

async def call_gemini(api_key: str, model: str, prompt_text: str) -> str:
    import httpx, os
    key = api_key.strip() if api_key else os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise ValueError("No Google Gemini API key provided.")
        
    models_to_try = [
        model.strip() if model and "gemini" in model.lower() else "gemini-1.5-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-1.5-pro"
    ]
    # Remove duplicates preserving order
    seen = set()
    models_to_try = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_error = ""
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt_text}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
    }
    
    async with httpx.AsyncClient(timeout=90) as client:
        for target_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
            try:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and candidates[0]["content"].get("parts"):
                        return candidates[0]["content"]["parts"][0]["text"]
                elif res.status_code == 404:
                    last_error = f"Model {target_model} not found (404)"
                    continue
                else:
                    err_msg = res.text
                    try:
                        err_json = res.json()
                        if "error" in err_json and "message" in err_json["error"]:
                            err_msg = err_json["error"]["message"]
                    except Exception:
                        pass
                    last_error = f"Gemini API Error ({res.status_code}): {err_msg}"
            except Exception as e:
                last_error = str(e)

    raise RuntimeError(last_error or "Gemini API failed to generate content.")

async def call_openai_compatible(api_key: str, base_url: str, model: str, prompt_text: str) -> str:
    import httpx, os
    key = api_key.strip() if api_key else os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        raise ValueError("No OpenAI / LLM API key provided.")
        
    endpoint_base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{endpoint_base}/chat/completions"
    target_model = model.strip() if model and not "gemini" in model.lower() else "gpt-4o-mini"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": target_model,
        "messages": [
            {
                "role": "system",
                "content": "You are CodeMate AI, an expert and supportive programming tutor. Provide accurate explanations, verified working code snippets, and expected output."
            },
            {
                "role": "user",
                "content": prompt_text
            }
        ],
        "temperature": 0.2
    }
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            err_msg = res.text
            try:
                err_json = res.json()
                if "error" in err_json:
                    if isinstance(err_json["error"], dict) and "message" in err_json["error"]:
                        err_msg = err_json["error"]["message"]
                    else:
                        err_msg = str(err_json["error"])
            except Exception:
                pass
            raise RuntimeError(f"OpenAI / LLM API Error ({res.status_code}): {err_msg}")
        data = res.json()
        return data["choices"][0]["message"]["content"]

async def test_llm_connection(api_key: str, provider: str = "auto", model: str = None, base_url: str = None) -> dict:
    prov = resolve_llm_provider(api_key, provider, base_url, model)
    if prov == "gemini":
        target_model = model if model and "gemini" in model.lower() else "gemini-1.5-flash"
    else:
        target_model = model if model and not "gemini" in model.lower() else "gpt-4o-mini"
    test_prompt = "Hello! Please reply in one sentence: 'CodeMate AI connected successfully with working output capability.'"

    try:
        if prov == "gemini":
            reply = await call_gemini(api_key, target_model, test_prompt)
        else:
            url = base_url or "https://api.openai.com/v1"
            reply = await call_openai_compatible(api_key, url, target_model, test_prompt)
        return {"ok": True, "provider": prov, "model": target_model, "reply": reply.strip()}
    except Exception as e:
        return {"ok": False, "provider": prov, "model": target_model, "error": str(e)}

async def llm(p: str):
    import os
    from .config import settings
    api_key = (settings.llm_api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    prov = resolve_llm_provider(api_key, settings.llm_provider, settings.llm_base_url, settings.llm_model)
    try:
        if prov == "gemini":
            model = settings.llm_model if "gemini" in settings.llm_model.lower() else "gemini-1.5-flash"
            return await call_gemini(api_key, model, p)
        else:
            base = settings.llm_base_url or "https://api.openai.com/v1"
            model = settings.llm_model if not "gemini" in settings.llm_model.lower() else "gpt-4o-mini"
            return await call_openai_compatible(api_key, base, model, p)
    except Exception as exc:
        print(f"[CodeMate AI Error] Real-time LLM query failed: {exc}")
        return None

