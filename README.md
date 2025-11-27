

# 🚀 Task Analyzer

### Prioritization + Dependency-Aware Scoring Engine

  

**Task Analyzer** is a lightweight, intelligent prioritization app. It accepts a raw list of tasks and returns a ranked, explainable order based on mathematical scoring strategies, automatically handling missing data, edge cases, and circular dependencies.

-----

## 🛠️ Setup Instructions (Start Here)

Follow these steps to get the application running on your local machine.

### 1\. Backend Setup (Django)

*Prerequisite: Python 3.12+ installed.*

1.  **Open your terminal (PowerShell)** and navigate to the backend folder:

    ```powershell
    cd "C:\python\Task Analyzer\backend"
    ```

2.  **Activate the Virtual Environment:**

    ```powershell
    ..\venv\Scripts\Activate.ps1
    ```

    *(If you see a security error, run `Set-ExecutionPolicy Unrestricted -Scope Process` first).*

3.  **Install Dependencies:**
    This installs Django, REST Framework, and CORS headers.

    ```powershell
    python -m pip install -U pip
    pip install -r requirements.txt
    ```

4.  **Initialize Database & Run Server:**

    ```powershell
    python manage.py migrate
    python manage.py runserver
    ```

    *✅ Backend is now running at `http://127.0.0.1:8000/`*

### 2\. Frontend Setup (HTML/CSS/JS)

*Prerequisite: None (Uses standard Python library).*

1.  Open a **new** terminal window.
2.  Navigate to the frontend folder:
    ```powershell
    cd "C:\python\Task Analyzer\frontend"
    ```
3.  Start a simple static server:
    ```powershell
    python -m http.server 5500
    ```
    *✅ UI is now live at `http://127.0.0.1:5500/`*

-----

## 📘 Documentation of Approach

Our approach moves beyond simple sorting by implementing a transparent, graph-aware **Weighted Sum Model**. Every task is evaluated against four normalized signals and combined using configurable strategies.

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

      * Yes. It combines quantitative data (dates, hours) with qualitative data (importance). By normalizing all inputs to a `0.0–1.0` scale, we ensure no single factor dominates unintentionally.

  * **How do you balance competing priorities (Urgent vs. Important)?**

      * We use **Configurable Strategies**. The default `smart_balance` strategy assigns weights of `0.40` to Urgency and `0.35` to Importance. This models the **Eisenhower Matrix**, ensuring high-urgency tasks take precedence without ignoring high-importance strategic work.

  * **How do you handle tasks with due dates in the past?**

      * "Past Due" is treated as **Maximum Urgency**. If `(Due Date - Today) < 0`, the urgency score is capped at `1.0` (100%). Overdue tasks naturally float to the top.

  * **What if a task has missing or invalid data? (Edge Cases)**

      * The system employs **"Graceful Degradation"**:
          * Invalid Dates $\rightarrow$ Treated as `None` (Score floor \~0.25).
          * Missing Importance $\rightarrow$ Defaults to `5` (Neutral).
          * Negative Hours $\rightarrow$ Defaults to `4.0` (Neutral effort).
      * *Result:* The algorithm never crashes; it returns a valid ranking + warnings.

  * **How do you detect circular dependencies?**

      * We implement **Depth First Search (DFS)**. We track node states: `0` (Unvisited), `1` (Visiting), `2` (Visited). If DFS encounters a node state of `1` (currently in stack), a cycle is confirmed.
      * *Result:* Tasks in a cycle get a **15% score penalty** to flag them as "Risky."

  * **Should your algorithm be configurable?**

      * **Yes.** We use the **Strategy Pattern**, allowing the frontend to pass a `strategy` parameter (e.g., `deadline_driven`) that hot-swaps the weight vectors ($W$) instantly.

### 3\. Test Case Scenarios

Here is how the algorithm handles specific real-world scenarios:

| Scenario | Input Data | Expected Outcome | Logic Used |
| :--- | :--- | :--- | :--- |
| **The "Crunch Time"** | Task A (Due Today, Imp 5)<br>Task B (Due Next Week, Imp 10) | **Task A ranks \#1** | Urgency weight (0.40) \> Importance weight (0.35) in `smart_balance`. |
| **The "Hidden Blocker"** | Task A (Imp 2, Blocks 5 tasks)<br>Task B (Imp 8, Blocks 0 tasks) | **Task A ranks \#1** | The "Blocker" score boosts Task A because finishing it unlocks 5 other items. |
| **The "Overdue"** | Task A (Due Yesterday)<br>Task B (Due Today) | **Task A ranks \#1** | Past due dates receive a capped urgency score of 1.0 + slight decay penalty for today. |
| **The "Cycle Trap"** | Task A depends on B<br>Task B depends on A | **Both Penalized** | The cycle is detected, and both tasks receive a 15% score reduction to warn the user. |

-----

## 🏆 Bonus Challenge: Data Intelligence

We focused strictly on the **Data Intelligence** challenge (30 min) to make the scoring engine smarter:

 **Date Intelligence:** The scoring engine now considers **weekends and holidays** (specifically Indian holidays) when calculating urgency. Instead of raw calendar days, it calculates "Working Days Remaining."


-----

## ⏱️ Development Time Log

| Component | Time Spent | Focus Area |
| :--- | :--- | :--- |
| **Backend Core** | **2 Hours** | Django setup, API endpoints, Scoring Logic, Unit Tests. |
| **Frontend UI** | **1 Hour** | HTML Structure, CSS Styling, JS Fetch Integration. |
| **Data Intelligence** | **30 Mins** | (Bonus) Strategy Weights, Cycle Detection, Explanation strings. |
| **Total** | **3.5 Hours** | End-to-end implementation. |

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

## 🚀 Future Improvements

With more time, we would implement:

  * **Persistence:** Add a database (PostgreSQL) and CRUD endpoints.
  * **User Accounts:** Authentication for private task boards.
  * **Capacity Planning:** Warn users if "Today's Focus" exceeds 8 hours.
  * **Export:** Download ranked lists as PDF/CSV.
  * **Visuals:** Critical Path visualization using D3.js.

<img width="1877" height="664" alt="image" src="https://github.com/user-attachments/assets/87c1ba98-16ae-4955-8765-0fa11bd51863" />
<img width="1779" height="610" alt="image" src="https://github.com/user-attachments/assets/062f2798-1055-48a8-9946-a1462bbee816" />
<img width="487" height="359" alt="image" src="https://github.com/user-attachments/assets/c4fc8856-6a58-4c77-a50b-ee79e4d34cad" />





