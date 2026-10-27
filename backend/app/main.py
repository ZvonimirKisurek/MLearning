from fastapi import FastAPI

app = FastAPI(title="MLE-Sprint API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
# Step 4 adds /briefing/today, /briefing/{id}/complete, /feed, /skills routers.
