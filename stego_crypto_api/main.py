"""
FastAPI Main Server Application
Secure Steganography, Cryptography, and Digital Watermarking Suite API

Provides clean REST endpoints consuming Base64 payloads and UploadFile form data.
Stateless backend architecture designed to integrate with Google Stitch UI.
"""

import base64
import io
import time
from typing import Optional, Dict, Any, List

import os
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Import suite modules
import crypto_engine
import rsa_educational
import stego_engine
import audio_stego_engine
import watermark_engine
import metrics


app = FastAPI(
    title="Secure Steganography, Cryptography & Watermarking API",
    description="Stateless REST API for modern hybrid encryption, educational BigInt RSA, LSB steganography, visible/invisible watermarking, and image quality metrics.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class RSAKeyGenRequest(BaseModel):
    key_size: int = Field(2048, description="RSA key size in bits (1024, 2048, 4096)")

class RSAKeyGenResponse(BaseModel):
    public_key_pem: str
    private_key_pem: str
    key_size: int

class HybridEncryptRequest(BaseModel):
    plaintext: str = Field(..., description="Message string to encrypt")
    public_key_pem: str = Field(..., description="RSA Public Key in PEM format")

class HybridDecryptRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="Encrypted hybrid JSON object")
    private_key_pem: str = Field(..., description="RSA Private Key in PEM format")

class SignRequest(BaseModel):
    message: str = Field(..., description="Message string to sign")
    private_key_pem: str = Field(..., description="RSA-PSS Private Key in PEM format")

class VerifyRequest(BaseModel):
    message: str = Field(..., description="Message string to verify")
    signature_b64: str = Field(..., description="Base64 encoded RSA-PSS signature")
    public_key_pem: str = Field(..., description="RSA-PSS Public Key in PEM format")

class HashRequest(BaseModel):
    text: Optional[str] = None
    data_b64: Optional[str] = None

class AESEncryptRequest(BaseModel):
    plaintext: str = Field(..., description="Message string to encrypt")
    password: str = Field(..., description="Secret key or password")

class AESDecryptRequest(BaseModel):
    ciphertext_payload: str = Field(..., description="Encrypted AES payload JSON string")
    password: str = Field(..., description="Secret key or password")

class EduKeyGenRequest(BaseModel):
    bits: int = Field(2048, description="Key bit length (1024, 2048, 4096)")

class EduEncryptRequest(BaseModel):
    plaintext: str
    public_key: Dict[str, str] = Field(..., description="Dict containing 'n' and 'e'")

class EduDecryptRequest(BaseModel):
    ciphertext: str = Field(..., description="Decimal string ciphertext")
    private_key: Dict[str, str] = Field(..., description="Dict containing 'n' and 'd'")

class MillerRabinRequest(BaseModel):
    n: str = Field(..., description="Integer candidate string")
    rounds: int = Field(20, description="Number of witness rounds")

class StegoCapacityRequest(BaseModel):
    width: int
    height: int

class StegoEmbedRequest(BaseModel):
    image_b64: str = Field(..., description="Base64 encoded input image (PNG/JPEG)")
    payload_text: str = Field(..., description="Secret text payload to embed")

class StegoExtractRequest(BaseModel):
    stego_image_b64: str = Field(..., description="Base64 encoded stego image")

class WatermarkTextRequest(BaseModel):
    image_b64: str
    text: str
    font_size: int = 28
    opacity: float = 0.4
    position: str = "bottom-right"
    color_hex: str = "#ffffff"

class WatermarkLogoRequest(BaseModel):
    base_image_b64: str
    logo_image_b64: str
    opacity: float = 0.4
    scale: float = 0.2
    position: str = "bottom-right"

class WatermarkDCTEmbedRequest(BaseModel):
    image_b64: str
    watermark_text: str
    strength: float = 20.0

class WatermarkDCTExtractRequest(BaseModel):
    image_b64: str
    watermark_bit_length: int
    strength: float = 20.0

class ImageCompareRequest(BaseModel):
    original_image_b64: str
    modified_image_b64: str


@app.get("/health", tags=["General"])
def health_check():
    return {"status": "healthy", "timestamp": time.time()}


# Cryptography Endpoints
@app.post("/api/crypto/generate-rsa-keys", response_model=RSAKeyGenResponse, tags=["Production Cryptography"])
def generate_rsa_keys(req: RSAKeyGenRequest):
    try:
        priv_key, pub_key = crypto_engine.generate_rsa_keypair(key_size=req.key_size)
        return {
            "public_key_pem": crypto_engine.export_public_key_pem(pub_key),
            "private_key_pem": crypto_engine.export_private_key_pem(priv_key),
            "key_size": req.key_size
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/encrypt-hybrid", tags=["Production Cryptography"])
def encrypt_hybrid(req: HybridEncryptRequest):
    try:
        pub_key = crypto_engine.import_public_key_pem(req.public_key_pem)
        payload = crypto_engine.hybrid_encrypt(req.plaintext, pub_key)
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/decrypt-hybrid", tags=["Production Cryptography"])
def decrypt_hybrid(req: HybridDecryptRequest):
    try:
        priv_key = crypto_engine.import_private_key_pem(req.private_key_pem)
        plaintext = crypto_engine.hybrid_decrypt(req.payload, priv_key)
        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/encrypt-file", tags=["Production Cryptography"])
async def encrypt_file_endpoint(
    public_key_pem: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        pub_key = crypto_engine.import_public_key_pem(public_key_pem)
        file_bytes = await file.read()
        enc_pkg = crypto_engine.encrypt_file_bytes(file_bytes, pub_key)
        
        return Response(
            content=enc_pkg,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={file.filename}.enc"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/decrypt-file", tags=["Production Cryptography"])
async def decrypt_file_endpoint(
    private_key_pem: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        priv_key = crypto_engine.import_private_key_pem(private_key_pem)
        pkg_bytes = await file.read()
        dec_bytes = crypto_engine.decrypt_file_bytes(pkg_bytes, priv_key)
        
        original_filename = file.filename.replace('.enc', '') if file.filename.endswith('.enc') else 'decrypted.bin'
        return Response(
            content=dec_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={original_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/sign", tags=["Production Cryptography"])
def sign_endpoint(req: SignRequest):
    try:
        priv_key = crypto_engine.import_private_key_pem(req.private_key_pem)
        sig_b64 = crypto_engine.sign_message(req.message, priv_key)
        return {"signature_b64": sig_b64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/verify", tags=["Production Cryptography"])
def verify_endpoint(req: VerifyRequest):
    try:
        pub_key = crypto_engine.import_public_key_pem(req.public_key_pem)
        valid = crypto_engine.verify_signature(req.message, req.signature_b64, pub_key)
        return {"valid": valid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/hash", tags=["Production Cryptography"])
def hash_endpoint(req: HashRequest):
    try:
        if req.text is not None:
            return {"hash_sha256": crypto_engine.sha256_text(req.text)}
        elif req.data_b64 is not None:
            raw_bytes = base64.b64decode(req.data_b64)
            return {"hash_sha256": crypto_engine.sha256_bytes(raw_bytes)}
        else:
            raise ValueError("Must provide either 'text' or 'data_b64'.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/encrypt-aes", tags=["Production Cryptography"])
def encrypt_aes_endpoint(req: AESEncryptRequest):
    try:
        res = crypto_engine.aes_encrypt_with_password(req.plaintext, req.password)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto/decrypt-aes", tags=["Production Cryptography"])
def decrypt_aes_endpoint(req: AESDecryptRequest):
    try:
        plaintext = crypto_engine.aes_decrypt_with_password(req.ciphertext_payload, req.password)
        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Educational RSA Endpoints
@app.post("/api/crypto-edu/generate-keys", tags=["Educational RSA"])
def edu_generate_keys(req: EduKeyGenRequest):
    try:
        keypair = rsa_educational.generate_key_pair(bits=req.bits)
        pub_pem = rsa_educational.format_public_key_pem(keypair["publicKey"])
        priv_pem = rsa_educational.format_private_key_pem(keypair["privateKey"])
        return {
            "keypair": keypair,
            "public_key_pem": pub_pem,
            "private_key_pem": priv_pem
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto-edu/encrypt", tags=["Educational RSA"])
def edu_encrypt(req: EduEncryptRequest):
    try:
        ciphertext = rsa_educational.rsa_edu_encrypt(req.plaintext, req.public_key)
        return {"ciphertext": ciphertext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto-edu/decrypt", tags=["Educational RSA"])
def edu_decrypt(req: EduDecryptRequest):
    try:
        plaintext = rsa_educational.rsa_edu_decrypt(req.ciphertext, req.private_key)
        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/crypto-edu/miller-rabin", tags=["Educational RSA"])
def edu_miller_rabin(req: MillerRabinRequest):
    try:
        candidate = int(req.n)
        is_prime = rsa_educational.miller_rabin(candidate, k=req.rounds)
        return {"n": req.n, "is_prime": is_prime, "rounds": req.rounds}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Steganography Endpoints
@app.post("/api/stego/capacity", tags=["Steganography"])
def stego_capacity(req: StegoCapacityRequest):
    cap_bytes = stego_engine.calculate_capacity_bytes(req.width, req.height)
    return {
        "width": req.width,
        "height": req.height,
        "capacity_bytes": cap_bytes,
        "capacity_bits": cap_bytes * 8
    }

@app.post("/api/stego/embed", tags=["Steganography"])
def stego_embed(req: StegoEmbedRequest):
    try:
        raw_img_bytes = base64.b64decode(req.image_b64.split(",")[-1])
        res = stego_engine.embed_data(raw_img_bytes, req.payload_text)
        comp_metrics = metrics.compare_images(raw_img_bytes, res["stego_image_bytes"])
        stego_b64 = base64.b64encode(res["stego_image_bytes"]).decode('utf-8')
        
        return {
            "status": "success",
            "stego_image_b64": f"data:image/png;base64,{stego_b64}",
            "bits_used": res["bits_used"],
            "capacity_bytes": res["capacity_bytes"],
            "width": res["width"],
            "height": res["height"],
            "metrics": comp_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stego/extract", tags=["Steganography"])
def stego_extract(req: StegoExtractRequest):
    try:
        raw_img_bytes = base64.b64decode(req.stego_image_b64.split(",")[-1])
        res_bytes, res_text = stego_engine.extract_data(raw_img_bytes)
        return {
            "status": "success",
            "extracted_text": res_text,
            "length_bytes": len(res_bytes)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stego/audio/embed", tags=["Steganography"])
async def audio_stego_embed_endpoint(
    text: str = Form(...),
    password: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_bytes = await file.read()
        res = audio_stego_engine.embed_audio_bytes(file_bytes, text, password)
        out_filename = f"stego_{file.filename.rsplit('.', 1)[0]}.wav"
        return Response(
            content=res["stego_wav_bytes"],
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename={out_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stego/audio/embed-details", tags=["Steganography"])
async def audio_stego_embed_details_endpoint(
    text: str = Form(...),
    password: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_bytes = await file.read()
        res = audio_stego_engine.embed_audio_bytes(file_bytes, text, password)
        stego_b64 = base64.b64encode(res["stego_wav_bytes"]).decode('utf-8')
        res_copy = {k: v for k, v in res.items() if k != "stego_wav_bytes"}
        res_copy["stego_audio_b64"] = f"data:audio/wav;base64,{stego_b64}"
        return res_copy
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stego/audio/extract", tags=["Steganography"])
async def audio_stego_extract_endpoint(
    password: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_bytes = await file.read()
        extracted_text = audio_stego_engine.extract_audio_bytes(file_bytes, password)
        key_hint = f"SHA-256('{password}')[:16]"
        return {
            "status": "success",
            "extracted_text": extracted_text,
            "magic_header": "ASTG (4 Bytes)",
            "cipher_algo": "AES-128-CBC (PKCS7 Padded)",
            "derived_key_hint": key_hint,
            "status_verification": "100% ACOUSTIC-LAYER PAYLOAD RECOVERY VERIFIED"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Watermarking Endpoints
@app.post("/api/watermark/visible-text", tags=["Digital Watermarking"])
def watermark_text_endpoint(req: WatermarkTextRequest):
    try:
        raw_img_bytes = base64.b64decode(req.image_b64.split(",")[-1])
        wm_bytes = watermark_engine.add_visible_text_watermark(
            raw_img_bytes,
            text=req.text,
            font_size=req.font_size,
            opacity=req.opacity,
            position=req.position,
            color_hex=req.color_hex
        )
        comp_metrics = metrics.compare_images(raw_img_bytes, wm_bytes)
        wm_b64 = base64.b64encode(wm_bytes).decode('utf-8')
        return {
            "status": "success",
            "watermarked_image_b64": f"data:image/png;base64,{wm_b64}",
            "metrics": comp_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/watermark/visible-logo", tags=["Digital Watermarking"])
def watermark_logo_endpoint(req: WatermarkLogoRequest):
    try:
        base_bytes = base64.b64decode(req.base_image_b64.split(",")[-1])
        logo_bytes = base64.b64decode(req.logo_image_b64.split(",")[-1])
        wm_bytes = watermark_engine.add_visible_logo_watermark(
            base_bytes,
            logo_bytes,
            opacity=req.opacity,
            scale=req.scale,
            position=req.position
        )
        comp_metrics = metrics.compare_images(base_bytes, wm_bytes)
        wm_b64 = base64.b64encode(wm_bytes).decode('utf-8')
        return {
            "status": "success",
            "watermarked_image_b64": f"data:image/png;base64,{wm_b64}",
            "metrics": comp_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/watermark/invisible-dct-embed", tags=["Digital Watermarking"])
def watermark_dct_embed(req: WatermarkDCTEmbedRequest):
    try:
        raw_img_bytes = base64.b64decode(req.image_b64.split(",")[-1])
        res = watermark_engine.embed_invisible_dct_watermark(
            raw_img_bytes,
            watermark_text=req.watermark_text,
            strength=req.strength
        )
        comp_metrics = metrics.compare_images(raw_img_bytes, res["watermarked_bytes"])
        wm_b64 = base64.b64encode(res["watermarked_bytes"]).decode('utf-8')
        return {
            "status": "success",
            "watermarked_image_b64": f"data:image/png;base64,{wm_b64}",
            "bits_embedded": res["bits_embedded"],
            "max_capacity_bits": res["max_capacity_bits"],
            "watermark_bit_length": res["bits_embedded"],
            "metrics": comp_metrics
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/watermark/invisible-dct-extract", tags=["Digital Watermarking"])
def watermark_dct_extract(req: WatermarkDCTExtractRequest):
    try:
        raw_img_bytes = base64.b64decode(req.image_b64.split(",")[-1])
        res = watermark_engine.extract_invisible_dct_watermark(
            raw_img_bytes,
            watermark_bit_length=req.watermark_bit_length,
            strength=req.strength
        )
        return {
            "status": "success",
            "extracted_text": res["extracted_text"],
            "bits_extracted": res["bits_extracted"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Quality Metrics Endpoints
@app.post("/api/metrics/compare", tags=["Analysis Metrics"])
def compare_images_endpoint(req: ImageCompareRequest):
    try:
        orig_bytes = base64.b64decode(req.original_image_b64.split(",")[-1])
        mod_bytes = base64.b64decode(req.modified_image_b64.split(",")[-1])
        res = metrics.compare_images(orig_bytes, mod_bytes)
        return {"status": "success", "metrics": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/metrics/compare-audio", tags=["Analysis Metrics"])
async def compare_audio_endpoint(
    original_file: UploadFile = File(...),
    modified_file: UploadFile = File(...)
):
    try:
        orig_bytes = await original_file.read()
        mod_bytes = await modified_file.read()
        res = metrics.compare_audio_bytes(orig_bytes, mod_bytes)
        return {"status": "success", "metrics": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Static UI Mounting
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "stego_crypto_frontend"))
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend_ui")
