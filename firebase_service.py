"""
Firebase Admin SDK를 이용한 Firestore 코멘트 저장소.

설계 포인트
----------
- 종목별로 서브컬렉션을 분리한다: tickers/{ticker}/comments/{commentId}
  이렇게 하면 조회 시 ticker에 대한 동등 조건(where) 없이 해당 서브컬렉션 안에서
  바로 order_by("time") 정렬만 하면 되므로, Firestore 복합 색인(composite index)을
  콘솔에서 별도로 만들 필요가 없다.
- 모든 접근은 서버(Flask)에서 Admin SDK로만 이루어지므로 Firestore 보안 규칙은
  관여하지 않는다(Admin SDK는 기본적으로 규칙을 우회한다). 따라서 보안 규칙도
  별도로 작성/배포할 필요가 없다.
- 인증은 serviceAccountKey.json 파일 하나만 사용한다. Firebase Authentication,
  Hosting, Storage 등 다른 Firebase 제품은 전혀 사용하지 않는다.

준비물
------
Firebase 콘솔에서 다음 두 가지만 하면 된다.
1) 프로젝트를 만들고 "Firestore Database"를 (네이티브 모드, 기본 설정으로) 한 번
   생성한다. 규칙/색인은 손대지 않아도 된다.
2) 프로젝트 설정 > 서비스 계정에서 새 비공개 키를 생성해 내려받은 JSON 파일을
   `serviceAccountKey.json` 으로 이름을 바꿔 이 프로젝트 루트(app.py와 같은 위치)에
   둔다.
"""
import os

import firebase_admin
from firebase_admin import credentials, firestore

_db = None


def _credential_path() -> str:
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "serviceAccountKey.json")


def get_db():
    global _db
    if _db is not None:
        return _db

    if not firebase_admin._apps:
        path = _credential_path()
        if not os.path.exists(path):
            raise RuntimeError(
                "serviceAccountKey.json 파일을 찾을 수 없습니다. "
                "Firebase 콘솔 > 프로젝트 설정 > 서비스 계정에서 키를 발급받아 "
                "프로젝트 루트에 'serviceAccountKey.json' 이름으로 저장해주세요."
            )
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)

    _db = firestore.client()
    return _db


def _comments_collection(ticker: str):
    return get_db().collection("tickers").document(ticker).collection("comments")


def _serialize_timestamp(value):
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def add_comment(ticker: str, comment_type: str, text: str, candle_time: int) -> dict:
    """코멘트를 추가하고, 저장된 문서(id 포함)를 반환한다."""
    doc_ref = _comments_collection(ticker).document()
    doc_ref.set(
        {
            "type": comment_type,
            "text": text,
            "time": candle_time,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    snapshot = doc_ref.get()
    data = snapshot.to_dict() or {}
    data["id"] = doc_ref.id
    data["createdAt"] = _serialize_timestamp(data.get("createdAt"))
    return data


def get_comments(ticker: str) -> list:
    """해당 종목의 코멘트를 시간순으로 모두 가져온다."""
    docs = _comments_collection(ticker).order_by("time").stream()
    results = []
    for doc in docs:
        item = doc.to_dict() or {}
        item["id"] = doc.id
        item["createdAt"] = _serialize_timestamp(item.get("createdAt"))
        results.append(item)
    return results


def delete_comment(ticker: str, comment_id: str) -> None:
    _comments_collection(ticker).document(comment_id).delete()
