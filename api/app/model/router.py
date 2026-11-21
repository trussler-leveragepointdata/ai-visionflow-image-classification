import os
from typing import List

from app import db
from app import settings as config
from app import utils
from app.auth.jwt import get_current_user
from app.model.schema import PredictRequest, PredictResponse
from app.model.services import model_predict
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

router = APIRouter(tags=["Model"], prefix="/model")


@router.post("/predict")
async def predict(
    file: UploadFile = File(None), current_user=Depends(get_current_user)
):
    rpse = {"success": False, "prediction": None, "score": None}

    if file is None or not file.filename or not utils.allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type is not supported.",
        )

    image_file_name = await utils.get_file_hash(file)
    image_path = os.path.join(config.UPLOAD_FOLDER, image_file_name)

    if not os.path.exists(image_path):
        with open(image_path, "wb") as image_file:
            image_file.write(await file.read())

    prediction, score = await model_predict(image_file_name)
    rpse.update(
        success=True,
        prediction=prediction,
        score=score,
        image_file_name=image_file_name,
    )

    return PredictResponse(**rpse)
