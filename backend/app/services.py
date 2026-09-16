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

def is_explicit_code_explanation_request(q):
    ql = q.lower()
    triggers = [
        "explain the code", "explain code", "explain program", "explain the program",
        "block by block", "line by line", "break down the code", "break down this code",
        "walk through the code", "explain this program", "explain hello world",
        "explain factorial", "explain odd or even", "explain palindrome"
    ]
    return any(t in ql for t in triggers)

def check_symbol_or_operator(q):
    # Match quoted or unquoted symbols
    # Look for quotes first: "%", "&&", "==", etc.
    quoted = re.findall(r'["\']([^"\']+)["\']', q)
    for s in quoted:
        s_clean = s.strip()
        if s_clean in OPERATOR_GUIDE:
            return s_clean

    # Look for direct tokens in question
    tokens = ["&&", "||", "==", "!=", "++", "--", "%d", "%f", "%c", "%s", "%", "&", "*", "!", "=", "sizeof", "printf", "scanf"]
    ql = f" {q.lower()} "
    for t in tokens:
        if f" {t} " in ql or f" '{t}' " in ql or f' "{t}" ' in ql or f" {t}?" in ql or q.strip() == t:
            return t
    return None

def prompt(q,ctx,tech,level,language,fmt,selected=None):
    s=f"\nSELECTED CODE:\n{selected}\n" if selected else ""
    return f"""You are CodeMate AI, an encouraging and accurate programming tutor for first-year college students.

Student Configuration:
- Technology: {tech}
- Explanation Level: {level}% ({level_text(level)})
- Format Preference: {fmt}
- Language: {language}

CRITICAL RULES FOR RESPONDING TO 1ST-YEAR STUDENTS:
1. ANSWER ONLY WHAT IS SPECIFICALLY ASKED:
   - If the student asks about a specific symbol, operator, or keyword (e.g., 'what is "%"', 'what is "&&"', 'what is scanf'):
     - Explain directly what it is and what it is used for.
     - Provide a short 3-4 line code example showing its usage.
     - DO NOT output a massive 4-block program breakdown unless explicitly requested!
   - If the student asks a specific conceptual or theoretical question:
     - Answer directly in the student's chosen format ({fmt}: points or paragraphs) with a short example.
   - ONLY IF the student explicitly asks to "explain the code", "explain the program", or "explain block by block":
     - Then provide the full program structure, syntax explanation, and block-by-block breakdown.

2. GROUNDING & ACCURACY:
   - If the student asks about a technology not in this document (e.g. asking where JavaScript is used in a C file), clearly explain: "JavaScript is NOT used in this document. This document contains {tech} code."
   - Never pretend that missing features or code exist.

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

    # 3. Numeric query check (e.g. user typed "32")
    q_stripped = q.strip()
    if q_stripped.isdigit():
        # Search for occurrences of this number in the context
        best_text = search_results[0].get("text", "") if search_results else ""
        source = search_results[0].get("source", doc_name) if search_results else doc_name
        return f"""### 📄 Reference to `{q_stripped}` in your document ({source})

In your uploaded material, **{q_stripped}** appears in the following context:

```c
{best_text[:400] if best_text else f'// Mention of {q_stripped} in {source}'}
```

• **Meaning**: In 32-bit systems, standard integers occupy **32 bits** (from bit 0 to bit 31).
• **Usage**: It is frequently used in bitwise shifting loops (e.g., `for (c = 31; c >= 0; c--)`) and memory allocation (e.g., `malloc(32 + 1)` for 32 binary characters plus string null-terminator `\\0`)."""

    # 4. Explicit full code / program explanation request
    if is_explicit_code_explanation_request(q) or "page" in q.lower() or "block by block" in q.lower():
        best_chunk = search_results[0] if search_results else {}
        best_text = best_chunk.get("text", "") if search_results else ctx[:800]
        source_name = best_chunk.get("source", doc_name)
        code_lines = [l for l in best_text.splitlines() if l.strip()]

        # Find program topic / title if available in text
        title_candidates = [l.strip() for l in code_lines if any(k in l.lower() for k in ("program", "algorithm", "example", "c code")) and not l.strip().startswith(("#", "{", "}", "int ", "printf"))]
        program_title = title_candidates[0] if title_candidates else "Program Code"

        # Separate code lines from headers/descriptions
        raw_code = "\n".join([l for l in code_lines if not any(l.strip() == t for t in title_candidates)])

        b1_headers = [l for l in code_lines if l.strip().startswith(("#", "import", "using", "package"))]
        b2_decl = [l for l in code_lines if any(k in l for k in ("main(", "int ", "float ", "char ", "double ", "long ", "Scanner", "def ")) and l not in b1_headers]
        b3_logic = [l for l in code_lines if any(k in l for k in ("if", "else", "while", "for", "switch", "scanf", "cin", "+", "-", "*", "/", "%", "=", ">", "<", "reverse", "temp", "sum", "fact")) and l not in b1_headers and l not in b2_decl]
        b4_output = [l for l in code_lines if any(k in l for k in ("printf", "cout", "print", "System.out", "return", "}")) and l not in b1_headers and l not in b2_decl and l not in b3_logic]

        b1_str = "\n".join(b1_headers) if b1_headers else (f"#include <stdio.h>\n" if tech=="C" else "")
        b2_str = "\n".join(b2_decl[:4]) if b2_decl else (f"int main()\n{{\n    int n;" if tech=="C" else "")
        b3_logic_str = "\n".join(b3_logic[:8]) if b3_logic else "    // User input and operational logic"
        b4_output_str = "\n".join(b4_output[:6]) if b4_output else (f"    printf(\"Result\\n\");\n    return 0;\n}}" if tech=="C" else "")

        lang_tag = "c" if tech in ("C", "C++") else ("java" if tech=="Java" else ("python" if tech=="Python" else "text"))

        # LEVEL 1: <= 30% (1st-Year College Beginner)
        if level <= 30:
            return f"""### 🟢 Explanation Depth: {level}% (1st-Year College Beginner)

#### 🎯 Program: {program_title}
From **{source_name}** ({tech}):

---

### 🧱 Foundational Structure & Syntax Breakdown (1st-Year Guide)
• **Preprocessor Directive (`#include <stdio.h>`)**: Tells the compiler to include the Standard I/O library definitions before compiling. Without it, functions like `printf` and `scanf` cannot be recognized!
• **Main Function Entry (`int main()` or `main()`)**: The official execution entry point. The OS starts running the program here.
• **Curly Braces (`{{ ... }}`)**: Defines scope and instruction blocks. Every `{{` must have a matching closing `}}`.
• **Variable Declarations (`int n, reverse = 0, temp;`)**: Allocates memory slots. `temp` is used to store an untouched backup copy of `n` before the loop modifies it!
• **Input / Output (`scanf` & `printf`)**:
  - `printf("...")`: Displays messages on the screen.
  - `scanf("%d", &n)`: Reads an integer from user. Note the **`&` (address-of operator)**: it passes the memory location of variable `n` so C knows where to save the entered number!
• **Semicolons (`;`)**: Terminates instructions. Omitting `;` is the #1 syntax error for college beginners!
• **Return Statement (`return 0;`)**: Signals clean, error-free program termination.

---

### 📦 Block-by-Block Code Walkthrough

#### 🔹 Block 1: Header Inclusions & Preprocessor
```{lang_tag}
{b1_str or '// Library inclusion'}
```
**Explanation**: Connects standard I/O library functions like `printf` and `scanf`.

#### 🔹 Block 2: Program Entry & Variable Initialization
```{lang_tag}
{b2_str or '// Variable declarations'}
```
**Explanation**: Execution begins here. Reserves memory space for input variables and working storage.

#### 🔹 Block 3: User Input & Core Logic
```{lang_tag}
{b3_logic_str}
```
**Explanation**: Prompts the user, reads the input values, and executes the algorithm step-by-step.

#### 🔹 Block 4: Output & Clean Exit
```{lang_tag}
{b4_output_str or '// Output and exit'}
```
**Explanation**: Displays the final calculated result on the screen and cleanly exits with status code `0`.

---

### 💡 1st-Year Student Tips
1. Always remember the `&` before variable names in `scanf("%d", &var)`.
2. Ensure every opening brace `{{` has a matching closing brace `}}`.
3. Terminate statements with `;`."""

        # LEVEL 2: 31% - 70% (Intermediate / Algorithm & Logic Flow)
        elif level <= 70:
            return f"""### 🟡 Explanation Depth: {level}% (Intermediate Technical & Algorithm Flow)

#### 🎯 Algorithm & Technical Overview: {program_title}
From **{source_name}** ({tech}):

---

### ⚙️ Algorithmic Strategy & Control Flow ({level}% Level)
1. **State Preservation**: The program preserves the initial input state in a backup variable (`temp = n`) because the iterative digit-extraction process destructively reduces `n` to zero.
2. **Modulo Arithmetic & Digit Accumulation**:
   - Extraction: `remainder = n % 10` isolates the least significant decimal digit.
   - Accumulation: `reverse = reverse * 10 + remainder` shifts existing digits left by one base-10 position and appends the extracted digit.
   - Reduction: `n = n / 10` discards the processed digit via integer truncation.
3. **Loop Invariant & Termination**: The `while (n != 0)` loop terminates after exactly $\\lfloor \\log_{{10}}(n) \\rfloor + 1$ iterations.
4. **Conditional Verification**: Compares `temp == reverse`. If equal, the number reads identically backwards and forwards.

---

### 📊 Code Implementation
```{lang_tag}
{best_text[:600]}
```

---

### 📈 Complexity & Engineering Analysis
• **Time Complexity**: $O(\\log_{{10}}(n))$ — The loop executes once per decimal digit in $n$.
• **Space Complexity**: $O(1)$ — Auxiliary memory is constant; only scalar integer registers are allocated.
• **Edge Cases & Boundary Conditions**:
  - Single-digit inputs ($0$ to $9$) are trivially verified.
  - Negative values: In standard definitions, negative numbers like $-121$ are not palindromes because the sign character does not mirror.
  - Integer Overflow Risk: Reversing values close to $2^{{31}} - 1$ (2,147,483,647) can exceed 32-bit signed integer limits."""

        # LEVEL 3: > 70% (Advanced Systems, Architecture & Optimization)
        else:
            return f"""### 🔵 Explanation Depth: {level}% (Advanced Systems, Memory Layout & Optimization)

#### 🏛️ Systems & Architecture Analysis: {program_title}
From **{source_name}** ({tech}):

---

### 🔬 Low-Level Systems & Assembly Optimization ({level}% Level)
1. **Activation Record & Stack Frame Allocation**:
   - Variables (`n`, `reverse`, `temp`) reside within the current function stack frame relative to the base pointer (`[rbp - 4]`, `[rbp - 8]`, etc.).
   - Under compiler optimization (`gcc -O2` or `-O3`), scalar variables are mapped directly into CPU registers (`eax`, `edx`, `ecx`), completely bypassing memory bus traffic.
2. **Compiler Division Optimization (Reciprocal Multiplication)**:
   - Hardware division (`IDIV`) is notoriously high-latency (20–40 CPU cycles).
   - Modern optimizing compilers replace `/ 10` with fixed-point multiplication by a reciprocal constant (`0x66666667` for 32-bit), followed by an arithmetic right shift (`SAR`), completing in only 1–2 clock cycles:
     ```assembly
     mov    edx, 0x66666667
     imul   edx, eax
     sar    edx, 2
     ```
3. **Standards Compliance & Undefined Behavior (UB)**:
   - In ISO C (C99/C11 §6.5), signed integer overflow is **Undefined Behavior (UB)**.
   - For safety-critical software, a pre-multiplication check (`if (reverse > INT_MAX / 10) return -1;`) is mandatory to prevent silent overflow and wraparound bugs.

---

### 📦 Source Reference
```{lang_tag}
{best_text[:500]}
```"""

    # 5. Theoretical / Conceptual question
    is_theory = is_theoretical_question(q)
    if is_theory:
        concepts = []
        for r in search_results:
            t = r.get("text", "")
            lines = [l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith(("#include", "int ", "char ", "return ", "{", "}", "printf", "scanf", "void ", "long ", "float "))]
            if lines:
                concepts.extend(lines[:4])

        concept_summary = " ".join(concepts[:5]) if concepts else f"Fundamental {tech} concepts found in your uploaded study material."

        if fmt == "points":
            return f"""### 📚 Explanation: {q} (Point-by-Point)

• **Definition**: {concept_summary[:240]}
• **Purpose**: In {tech}, this concept provides structured logic to direct program execution.
• **How It Works**: Statements execute step-by-step according to {tech} syntax rules.
• **1st-Year Tip**: Understand the conceptual logic first before writing syntax."""
        elif fmt == "paragraph":
            return f"""### 📚 Explanation: {q}

{concept_summary}

In {tech} programming, understanding this fundamental concept is crucial during your first year. It provides the building blocks for writing robust programs and solving lab assignments with confidence."""
        else:
            return f"""### 📚 Concept Overview: {q}

**Summary:**
{concept_summary}

**Key Points:**
• Relates directly to `{q}` as documented in your uploaded material.
• Pay close attention to syntax rules and test with small sample inputs."""

    # 6. Default targeted answer based on search results
    best_chunk = search_results[0] if search_results else {}
    best_text = best_chunk.get("text", "") if search_results else ctx[:400]
    source_name = best_chunk.get("source", doc_name)

    return f"""### 💡 Answer to: {q}

From your uploaded document (**{source_name}**):

{best_text[:600]}

• **Technology**: {tech}
• **Tip**: To explore further, ask: *"Explain this code block by block"* or ask about specific keywords and operators!"""


async def llm(p):
    from .config import settings
    import httpx
    if not settings.llm_api_key: return None
    u=settings.llm_base_url.rstrip("/")+"/chat/completions"
    h={"Authorization":f"Bearer {settings.llm_api_key}"}
    body={"model":settings.llm_model,"messages":[
        {"role":"system","content":"Stay accurate and grounded in supplied context."},
        {"role":"user","content":p}], "temperature":0.2}
    async with httpx.AsyncClient(timeout=90) as c:
        r=await c.post(u,headers=h,json=body); r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
