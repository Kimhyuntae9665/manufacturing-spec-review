# 현재 화면 갤러리 · P09 v2 시각 기준 적용

원본 UI 코드를 실행한 Chrome의 실제 캡처입니다. 기준 사양과 후보 도면은 합성 문서입니다. 01–07은 규칙 기준선 또는 명시된 브라우저 응답 mock, 08–11은 기존 실제 모델 비교를 SQLite 복사본에서 GET으로 읽은 결과입니다. 이 재캡처 중 **새 모델 요청 0회**입니다. 01·06·07은 설명하는 기능이 화면 안에 들어오도록 같은 브라우저 검사를 한 번 더 실행해 해당 PNG만 교체했습니다. [별도 재촬영 기록](framing-recapture.json)은 이 세 파일에만 적용되며 다른 이미지와 영상은 원래 촬영본입니다.

[현재 영상](video/nota-workflow.mp4)은 Chrome screencast의 원본 프레임 순서와 획득 시간을 보존해 무음 MP4로 인코딩했습니다. [프레임·장면 manifest](video/native-frames.json), [인코딩 검증](video/probe.json), [전체 파일 SHA-256](checksums.sha256)을 함께 제공합니다. 재현 스크립트는 [scripts/refit_capture.py](../../../scripts/refit_capture.py)이며 격리된 loopback 19102/19112와 임시 SQLite 복사본을 사용합니다. 프로젝트 원본 저장 결과와 서버 설정은 바꾸지 않습니다.

| 순서 | 현재 기능/상태 | 출처 |
|---|---|---|
| [01 원문과 개정](01-reference-candidate-provenance.png) | 승인 기준·후보 초안 원문 두 칸, 문서 개정과 해시 | 원문 조회 |
| [02 명목 환산](02-declared-nominal-conversion.png) | 10 µm 대 0.010 mm | 규칙 기준선 |
| [03 재질 차이](03-material-notation-difference.png) | SUS304 대 SUS304L | 규칙 기준선 |
| [04 차이와 누락](04-finish-difference-missing-thickness.png) | ZN_NI 대 NI, 빈 두께 | 규칙 기준선 |
| [05 검토·이력](05-followup-record-and-audit.png) | 후속 확인 기록과 중복 제출 차단 | 규칙 기준선 |
| [06 모의 실패](06-mock-failure-manual-confirmation.png) | 수동 확인 체크와 두 기록 버튼 표시; 체크 전 차단은 회귀 검사 | 브라우저 응답 mock, 실제 모델 아님 |
| [07 모바일](07-mobile-source-workspace.png) | 390px 원문·선택 | 규칙 기준선 |
| [08 실제 실패](08-real-model-failure-manual-review.png) | 저장된 과거 인용 오류 | 실제 모델 결과 GET |
| [09 모델 P001](09-stored-real-model-p001.png) | 저장된 과거 명목 단위 추출 | 실제 모델 결과 GET |
| [10 모델 P002](10-stored-real-model-p002.png) | 저장된 과거 재질 표기 차이 | 실제 모델 결과 GET |
| [11 모델 P003](11-stored-real-model-p003.png) | 저장된 과거 표면처리·두께 누락 | 실제 모델 결과 GET |

재캡처 검증: 기존 Python 단위/HTTP 테스트 72개 통과, Chrome UI 회귀 통과, 모바일 390px 가로 넘침 없음, 텍스트 최소 14px·계산 대비 최소 4.63:1, 축소 동작 존중, engineer 검토 쓰기 차단, 검토 반복 전송 차단. 측정값과 상태는 [result.json](result.json)에 기록했습니다. 데모 역할 선택은 실제 인증이 아닙니다. 이전 [화면 갤러리](../README.md)와 영상은 이전 UI의 역사적 자료로 유지합니다.
