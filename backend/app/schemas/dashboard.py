from pydantic import BaseModel

class DashboardOut(BaseModel):
    totals: dict
    recent_records: list
