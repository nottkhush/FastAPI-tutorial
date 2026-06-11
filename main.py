from fastapi import FastAPI, Query
from datetime import datetime
from typing import Any
from fastapi import Request
from sqlmodel import SQLModel, create_engine, Session, func
from typing_extensions import Annotated
from fastapi import Depends
from contextlib import asynccontextmanager
from sqlmodel import select
from sqlmodel import Field
from datetime import timezone
from pydantic import BaseModel
from fastapi import HTTPException
from typing import TypeVar, Generic

T = TypeVar("T")


class Campaign(SQLModel, table=True):
    campaign_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    due_date: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=True, index=True
    )


class CampaignCreate(SQLModel):
    name: str
    due_date: datetime | None = Field(default=None)


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_dn_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_dn_and_tables()
    with Session(engine) as session:
        if not session.exec(select(Campaign)).first():
            session.add_all(
                [
                    Campaign(name="Summer Launch", due_date=datetime.now()),
                    Campaign(name="Cold Campaign", due_date=datetime.now()),
                    Campaign(name="Diwali Campaign", due_date=datetime.now()),
                ]
            )
            session.commit()
    yield


app = FastAPI(root_path="/api/v1", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World!"}


data: Any = [
    {
        "campaign_id": 1,
        "name": "Summer Launch",
        "due_date": datetime.now(),
        "created_at": datetime.now(),
    },
    {
        "campaign_id": 2,
        "name": "Cold Campaign",
        "due_date": datetime.now(),
        "created_at": datetime.now(),
    },
    {
        "campaign_id": 3,
        "name": "Diwali Campaign",
        "due_date": datetime.now(),
        "created_at": datetime.now(),
    },
]


class Response(BaseModel, Generic[T]):
    data: T


class PaginatedResponse(BaseModel, Generic[T]):
    data: T
    next: str | None
    prev: str | None


@app.get("/campaigns", response_model=PaginatedResponse[list[Campaign]])
async def read_campaigns(
    request: Request,
    session: SessionDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1),
):
    
    data = session.exec(
        select(Campaign).order_by(Campaign.campaign_id).offset(offset).limit(limit)
    ).all()  # type is ignored
    base_url = str(request.url).split("?")[0]

    if offset > 0:
        prev_url = f"{base_url}?offset={max(0, offset-limit)}&limit={limit}"
    else:
        prev_url = None

    next_url = f"{base_url}?offset={offset+limit}&limit={limit}"
    
    print(next_url, prev_url)

    return {"data": data, "next": next_url, "prev": prev_url}


@app.get("/campaigns/{id}", response_model=Response[Campaign])
async def read_campaign(id: int, session: SessionDep):
    data = session.get(Campaign, id)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": data}


@app.post("/campaigns", status_code=201, response_model=Response[Campaign])
async def create_campaign(campaign: CampaignCreate, session: SessionDep):
    db_campaign = Campaign.model_validate(campaign)
    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)
    return {"data": db_campaign}


@app.put("/campaigns/{id}", response_model=Response[Campaign])
async def update_campaign(id: int, campaign: CampaignCreate, session: SessionDep):
    data = session.get(Campaign, id)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")

    data.name = campaign.name
    data.due_date = campaign.due_date
    session.add(data)
    session.commit()
    session.refresh(data)
    return {"data": data}


@app.delete("/campaigns/{id}", status_code=204)
async def delete_campaign(id: int, session: SessionDep):
    data = session.get(Campaign, id)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    session.delete(data)
    session.commit()
