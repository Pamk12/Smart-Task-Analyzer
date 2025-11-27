

# 🚀 Task Analyzer

### Prioritization + Dependency-Aware Scoring Engine

  

**Task Analyzer** is a lightweight, intelligent prioritization app. It accepts a raw list of tasks and returns a ranked, explainable order based on mathematical scoring strategies, automatically handling missing data, edge cases, and circular dependencies.

-----

## 📘 Documentation of Approach

Our approach moves beyond simple sorting by implementing a transparent, graph-aware **Weighted Sum Model**. Instead of a black box, every task is evaluated against four normalized signals and combined using strategy-specific weights.

### 1\. The Mathematical Constraint

The ranking is determined by a linear equation where $W$ represents the configurable weight of a strategy:

```math
Score = (W_{urgency} \times U) + (W_{importance} \times I) + (W_{quickwin} \times Q) + (W_{blocker} \times B)
```

  * **$U$ (Urgency):** Logistic decay function (closer deadline = higher score).
  * **$I$ (Importance):** Normalized user value (1–10).
  * **$Q$ (Quick Win):** Logarithmic scaling (shorter estimated hours = slight boost).
  * **$B$ (Blocker):** Graph traversal count (more downstream dependents = higher score).

### 2\. Algorithmic Deep Dive & Logic

We addressed the specific challenges of prioritization as follows:

  * **Does the scoring logic make sense?**

      * Yes. It combines quantitative data (dates, hours) with qualitative data (importance). By normalizing all inputs to a `0.0–1.0` scale before weighting, we ensure no single factor mathematically dominates the others unintentionally.

  * **How do you balance competing priorities (Urgent vs. Important)?**

      * We use **Configurable Strategies**. The default `smart_balance` strategy assigns weights of `0.40` to Urgency and `0.35` to Importance. This mathematically models the **Eisenhower Matrix**, ensuring high-urgency tasks take precedence while preventing high-importance tasks from being ignored.

  * **How do you handle tasks with due dates in the past?**

      * We treat "Past Due" as **Maximum Urgency**. If `(Due Date - Today) < 0`, the urgency score is immediately capped at `1.0` (100%). Overdue tasks naturally float to the top unless they are significantly blocked or extremely low value.

  * **What if a task has missing or invalid data? (Edge Cases)**

      * The system employs a strict **Normalization Layer** ("Graceful Degradation").
          * Invalid Dates $\rightarrow$ Treated as `None` (Score floor \~0.25).
          * Missing Importance $\rightarrow$ Defaults to `5` (Neutral).
          * Negative Hours $\rightarrow$ Defaults to `4.0` (Neutral effort).
      * *Result:* The algorithm never crashes on bad input; it returns a valid ranking + warning messages.

  * **How do you detect circular dependencies?**

      * We implement **Depth First Search (DFS)**. We track node states: `0` (Unvisited), `1` (Visiting), `2` (Visited). If DFS encounters a node state of `1` (currently in the recursion stack), a cycle is confirmed.
      * *Result:* Tasks in a cycle get a **15% score penalty** to flag them as "Risky/Blocked" rather than crashing the scheduler.

  * **Should your algorithm be configurable?**

      * **Yes.** User needs change (e.g., "Crunch Time" vs. "Strategic Planning"). We use the **Strategy Pattern**, allowing the frontend to pass a `strategy` parameter (e.g., `deadline_driven`) that hot-swaps the weight vectors ($W$) instantly.

-----

## ⏱️ Development Time Log

| Component | Time Spent | Focus Area |
| :--- | :--- | :--- |
| **Backend Core** | **2 Hours** | Django setup, API endpoints, Scoring Logic, Unit Tests. |
| **Frontend UI** | **1 Hour** | HTML Structure, CSS Styling, JS Fetch Integration. |
| **Data Intelligence** | **30 Mins** | (Bonus) Strategy Weights, Cycle Detection, Explanation strings. |
| **Total** | **3.5 Hours** | End-to-end implementation. |

-----

## 🛠️ Setup Instructions

### 1\. Backend (Django)

*Prerequisite: Python 3.12+*

```powershell
# 1. Navigate to backend and activate virtual environment
cd "C:\python\Task Analyzer\backend"
..\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize Database & Run
python manage.py migrate
python manage.py runserver
```

*Server runs at `http://127.0.0.1:8000/`*

### 2\. Frontend (HTML/CSS/JS)

```powershell
# 1. Navigate to frontend folder
cd "C:\python\Task Analyzer\frontend"

# 2. Start simple server
python -m http.server 5500
```

*UI runs at `http://127.0.0.1:5500/`*

-----

## 📡 API Usage

### 📊 Analyze Tasks

**POST** `/api/tasks/analyze/?strategy=smart_balance`

**Payload:**

```json
[
  {
    "id": 1, 
    "title": "Fix login bug", 
    "due_date": "2025-11-30", 
    "estimated_hours": 3,
    "importance": 8,
    "dependencies": []
  },
  {
    "id": 2, 
    "title": "Write report", 
    "dependencies": [1]
  }
]
```

-----

## 🧩 Design Decisions

  * **Explainability:** The API returns an `explanation` string (e.g., *"U=85%, I=60%"*) so users trust the ranking.
  * **Robustness:** The graph algorithm (DFS) ensures that even complex dependency webs don't break the application.
  * **Simplicity:** HTML/CSS/JS was chosen over React/Vue to reduce setup friction (no `npm install`) and strictly adhere to the time constraints.
    
🚀 Future Roadmap
[ ] User Accounts: Save task boards per user.

[ ] Persistence: Add Database CRUD (Create/Read/Update/Delete) for tasks.

[ ] Capacity Planning: Warn users if "Today's Focus" exceeds 8 hours.

[ ] Export: Download reports as PDF/CSV.

[ ] Visuals: Critical Path visualization using D3.js or Canvas.


