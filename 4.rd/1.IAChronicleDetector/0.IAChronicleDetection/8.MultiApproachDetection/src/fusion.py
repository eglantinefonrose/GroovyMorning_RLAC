from loguru import logger

class FusionEngine:
    def __init__(self, thresholds):
        self.thresholds = thresholds
        self.state = "IDLE" # IDLE, SUSPICION, DETECTED
        self.history = []

    def fuse(self, scores, offset=None):
        """
        Combine scores from different modules.
        scores: dict {novelty, music, speaker, semantic}
        offset: float (seconds from start)
        """
        weights = {
            "novelty": 0.2,
            "music": 0.2,
            "speaker": 0.2,
            "semantic": 0.4
        }

        # Calculate weighted average
        total_score = sum(scores.get(k, 0) * weights[k] for k in weights)

        timestamp = ""
        if offset is not None:
            mins = int(offset // 60)
            secs = int(offset % 60)
            timestamp = f"[{mins:02d}:{secs:02d}] "

        # Log individual contributions
        logger.info(f"{timestamp}Fusion Scores - Total: {total_score:.2f} | N: {scores.get('novelty'):.2f} | M: {scores.get('music'):.2f} | S: {scores.get('speaker'):.2f} | LLM: {scores.get('semantic'):.2f}")

        decision = {
            "total_score": total_score,
            "is_detected": total_score >= self.thresholds.get("combined_threshold", 0.75),
            "state": self.state,
            "new_detection": False
        }

        # State machine logic
        if decision["is_detected"]:
            if self.state == "IDLE":
                self.state = "DETECTED"
                decision["new_detection"] = True
                logger.success(f"{timestamp}>>> CHRONICLE DETECTED <<<")
            else:
                self.state = "DETECTED"
        else:
            self.state = "IDLE"

        decision["state"] = self.state
        return decision
