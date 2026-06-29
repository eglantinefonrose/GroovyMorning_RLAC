
# Information

## Model used
whisper_ggml-large-v3-turbo

## Command used
```bash
export PRTLABS_HOME=/Users/eglantine/Dev/0.perso/2.Proutechos
export MODEL_BASEPATH=${PRTLABS_HOME}/9.GroovyMorning/4.rd/@assets/whisper.cpp/models
export ASSET_BASEPATH=${PRTLABS_HOME}/9.GroovyMorning/4.rd/@assets
export TRANSCRIPTION_BASEPATH=${PRTLABS_HOME}/9.GroovyMorning/4.rd/@assets/transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo
export AUDIO_FILE=23134-25.03.2026-ITEMA_24436867-2026F10761S0084-NET_MFI_32D227A4-B7EA-4EDD-80C4-BA81A34E8C0A-22-d9fd0e1937d3142a0e4a2c9401c3b5d0

whisper-cli -m ${MODEL_BASEPATH}/ggml-large-v3-turbo.bin -f ${ASSET_BASEPATH}/${AUDIO_FILE}.mp3 > ${TRANSCRIPTION_BASEPATH}/${AUDIO_FILE}_transcription.srt
```
