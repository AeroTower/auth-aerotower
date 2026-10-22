from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    # `sub` da conta Google: nunca muda, mesmo que a pessoa troque de e-mail.
    id        = Column(String, primary_key=True)
    email     = Column(String, nullable=True, index=True)
    nome      = Column(String, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.now)


class Torre(Base):
    __tablename__ = "torres"

    id           = Column(String, primary_key=True)          # AT-<MAC do ESP32>
    kit          = Column(String, nullable=False)            # basico | completo | pro
    # Hash do codigo do adesivo (o texto puro so existe no adesivo).
    codigo_hash  = Column(String, nullable=False, unique=True, index=True)
    dono_id      = Column(String, ForeignKey("usuarios.id"), nullable=True, index=True)
    apelido      = Column(String, nullable=True)
    criada_em    = Column(DateTime, nullable=False, default=datetime.now)
    vinculada_em = Column(DateTime, nullable=True)
    # Sobe a cada mudanca. Vai no evento: o Backend ignora evento mais velho
    # do que o que ja aplicou.
    versao       = Column(Integer, nullable=False, default=1)

    def estado(self) -> dict:
        """Estado completo, o que vai nos eventos (consumidor idempotente)."""
        return {
            "id":      self.id,
            "kit":     self.kit,
            "donoId":  self.dono_id,
            "apelido": self.apelido,
            "versao":  self.versao,
        }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
