"""景区内容管理API — 酒店介绍/房型实景/周边推荐"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.api.auth import get_current_user
from app.db import User
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter(prefix="/api/content", tags=["内容管理"])

# ---- 简单JSON存储方案(不需要新数据库表) ----
CONTENT_FILE = "/home/ubuntu/projects/scenic/data/content.json"

def _load():
    try:
        with open(CONTENT_FILE) as f:
            return json.load(f)
    except:
        return {"hotels":[],"galleries":[],"surroundings":[],"reviews_show":[]}

def _save(d):
    with open(CONTENT_FILE,"w") as f:
        json.dump(d,f,ensure_ascii=False)

# ======== 酒店介绍 ========
class HotelIntro(BaseModel):
    hotel_id: int
    name: str
    desc: str = ""
    cover: str = ""
    features: list[str] = []
    facilities: list[str] = []
    checkin_time: str = "14:00"
    checkout_time: str = "12:00"

@router.get("/hotels")
async def list_hotel_intros(hotel_id:int=0):
    d=_load();h=d["hotels"]
    if hotel_id: h=[x for x in h if x.get("hotel_id")==hotel_id]
    return h

@router.post("/hotels")
async def save_hotel_intro(req:HotelIntro, user:User=Depends(get_current_user)):
    d=_load()
    for i,x in enumerate(d["hotels"]):
        if x.get("hotel_id")==req.hotel_id:
            d["hotels"][i]=req.model_dump()
            _save(d)
            return {"ok":True,"id":req.hotel_id}
    d["hotels"].append(req.model_dump())
    _save(d)
    return {"ok":True,"id":req.hotel_id}

# ======== 房型实景 ========
class RoomGallery(BaseModel):
    room_id: int
    room_name: str
    images: list[str] = []
    video: str = ""
    vr_url: str = ""
    desc: str = ""
    amenities: list[str] = []
    perks: list[str] = []

@router.get("/gallery")
async def list_galleries(room_id:int=0):
    d=_load();g=d["galleries"]
    if room_id: g=[x for x in g if x.get("room_id")==room_id]
    return g

@router.post("/gallery")
async def save_gallery(req:RoomGallery, user:User=Depends(get_current_user)):
    d=_load()
    for i,x in enumerate(d["galleries"]):
        if x.get("room_id")==req.room_id:
            d["galleries"][i]=req.model_dump()
            _save(d)
            return {"ok":True}
    d["galleries"].append(req.model_dump())
    _save(d)
    return {"ok":True}

# ======== 周边推荐 ========
class Surrounding(BaseModel):
    name: str
    type: str = "餐饮"
    address: str = ""
    distance: str = ""
    rating: float = 4.5
    image: str = ""
    desc: str = ""
    lat: float = 0
    lng: float = 0
    phone: str = ""

@router.get("/surrounding")
async def list_surroundings(type:str=""):
    d=_load();s=d["surroundings"]
    if type: s=[x for x in s if x.get("type")==type]
    return s

@router.post("/surrounding")
async def upsert_surrounding(req:Surrounding, user:User=Depends(get_current_user)):
    d=_load()
    found=False
    for i,x in enumerate(d["surroundings"]):
        if x.get("name")==req.name:
            d["surroundings"][i]=req.model_dump()
            found=True;break
    if not found: d["surroundings"].append(req.model_dump())
    _save(d)
    return {"ok":True}

@router.delete("/surrounding")
async def del_surrounding(name:str, user:User=Depends(get_current_user)):
    d=_load()
    d["surroundings"]=[x for x in d["surroundings"] if x.get("name")!=name]
    _save(d)
    return {"ok":True}

# ======== 评价展示管理 ========
class ReviewShow(BaseModel):
    user_name: str
    rating: int
    content: str
    images: list[str] = []
    date: str = ""

@router.get("/reviews-show")
async def list_reviews_show():
    d=_load()
    return d.get("reviews_show",[])

@router.post("/reviews-show")
async def add_review_show(req:ReviewShow, user:User=Depends(get_current_user)):
    d=_load()
    d.setdefault("reviews_show",[]).append(req.model_dump())
    _save(d)
    return {"ok":True}

@router.delete("/reviews-show")
async def del_review_show(index:int, user:User=Depends(get_current_user)):
    d=_load()
    rs=d.get("reviews_show",[])
    if 0<=index<len(rs):rs.pop(index)
    d["reviews_show"]=rs
    _save(d)
    return {"ok":True}
