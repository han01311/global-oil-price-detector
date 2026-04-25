#!/bin/bash

# Native Ollama 기반 Gemma 모델 풀링 스크립트 (Mac GPU 최적화)

if ! command -v ollama &> /dev/null
then
    echo "[!] Ollama 명령어를 찾을 수 없습니다."
    echo "아래 명령어로 설치하시거나 (Homebrew 권장) Mac 전용 앱을 받아주세요:"
    echo "brew install ollama"
    exit 1
fi

echo "[1/2] Ollama 서비스가 데몬으로 띄워져 있는지 확인/시작합니다..."
# Homebrew 셋업의 경우 'brew services start ollama' 사용을 권장합니다.
# 이미 Mac Native App이 켜져 있으면 아래 통신 테스트가 통과합니다.
if ! curl -s http://localhost:11434/ > /dev/null; then
    echo "Ollama 백그라운드 서버를 실행합니다..."
    nohup ollama serve > /dev/null 2>&1 &
    sleep 3
fi

echo "[2/2] Native Ollama 환경에서 Gemma 모델 가중치를 다운로드합니다..."
ollama pull gemma

echo "======================================"
echo "✨ 로컬 Native Gemma 모델 세팅 및 구동이 완료되었습니다!"
echo "API 서버 주소: http://localhost:11434"
echo "이제 사용자의 Mac(Apple Silicon/GPU) 리소스를 100% 활용합니다."
echo "======================================"
