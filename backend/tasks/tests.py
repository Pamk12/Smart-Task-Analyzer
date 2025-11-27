from django.test import TestCase
from datetime import date
from .scoring import normalize_tasks, score_tasks

class ScoringTests(TestCase):
    
    # ... keep your existing tests ...

    def test_holiday_impact_on_urgency(self):
        """
        Test that Indian holidays reduce 'working days', making a task MORE urgent
        than a task with the same calendar duration but no holidays.
        """
        # Scenario A: October 1st to Oct 3rd (Includes Oct 2nd Gandhi Jayanti Holiday)
        # Timeline: Oct 1 (Work), Oct 2 (Holiday), Oct 3 (Due).
        # Available Working Days: 1
        today_holiday = date(2025, 10, 1)
        task_holiday = {
            "id": 1, 
            "title": "Holiday Crunch", 
            "due_date": "2025-10-03", 
            "estimated_hours": 2, 
            "importance": 5, 
            "dependencies": []
        }

        # Scenario B: November 5th to Nov 7th (Normal Wed-Fri)
        # Timeline: Nov 5 (Work), Nov 6 (Work), Nov 7 (Due).
        # Available Working Days: 2
        today_normal = date(2025, 11, 5)
        task_normal = {
            "id": 2, 
            "title": "Normal Week", 
            "due_date": "2025-11-07", 
            "estimated_hours": 2, 
            "importance": 5, 
            "dependencies": []
        }

        # Score them independently with their respective 'today' dates
        norm_h, _ = normalize_tasks([task_holiday])
        score_h = score_tasks(norm_h, today=today_holiday)["tasks"][0]["score"]

        norm_n, _ = normalize_tasks([task_normal])
        score_n = score_tasks(norm_n, today=today_normal)["tasks"][0]["score"]

        # The Holiday task has fewer working days (1 vs 2), so it should be MORE urgent/higher score
        self.assertGreater(score_h, score_n, "Holidays should increase urgency by reducing working days")

    def test_downstream_blocker_boost(self):
        """
        Test that a task blocking other tasks (bottleneck) scores higher 
        than an isolated task with identical stats.
        """
        raw = [
            # Task 1 blocks Task 2 and Task 3
            {"id": 1, "title": "Bottleneck", "due_date": "2025-12-01", "estimated_hours": 4, "importance": 5, "dependencies": []},
            {"id": 2, "title": "Blocked A", "due_date": "2025-12-05", "estimated_hours": 4, "importance": 5, "dependencies": [1]},
            {"id": 3, "title": "Blocked B", "due_date": "2025-12-05", "estimated_hours": 4, "importance": 5, "dependencies": [1]},
            
            # Task 4 blocks nothing
            {"id": 4, "title": "Lone Wolf", "due_date": "2025-12-01", "estimated_hours": 4, "importance": 5, "dependencies": []},
        ]

        tasks, _ = normalize_tasks(raw)
        # Use 'high_impact' or 'smart_balance' as they weight blockers. 
        # 'deadline_driven' barely cares about blockers (0.02 weight).
        out = score_tasks(tasks, strategy="smart_balance")
        
        results = {t["id"]: t["score"] for t in out["tasks"]}
        
        # Task 1 (Bottleneck) must be higher than Task 4 (Lone Wolf)
        self.assertGreater(results[1], results[4])

    def test_normalization_resilience(self):
        """
        Test that the API normalizes garbage data (strings, bad dates) 
        instead of crashing, and returns warnings.
        """
        raw_garbage = [
            {
                "id": "100",           # String ID (should become int 100)
                "title": "Messy Task",
                "due_date": "Tomorrow", # Invalid Date (should become None)
                "estimated_hours": -5,  # Negative hours (should become None)
                "importance": "High",   # String importance (should become 5)
                "dependencies": "None"  # String deps (should become [])
            }
        ]

        normalized_tasks, warnings = normalize_tasks(raw_garbage)
        scored_result = score_tasks(normalized_tasks)

        task = scored_result["tasks"][0]

        # Assertions for Data Correction
        self.assertEqual(task["id"], 100)
        self.assertIsNone(task["due_date"])        # Invalid date becomes None
        self.assertEqual(task["importance"], 5)    # "High" becomes default 5
        self.assertEqual(task["dependencies"], []) # "None" becomes empty list

        # Assertions for Warnings
        self.assertTrue(len(warnings) > 0)
        self.assertIn("invalid due_date", warnings[0])