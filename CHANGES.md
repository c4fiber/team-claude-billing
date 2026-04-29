# 문서 패치 — Members Count SSoT 통합 반영

이 패치는 코드 변경(SSoT 통합)에 맞춰 문서를 동기화합니다.
**ssot_improvement.zip 패치 적용 후에 이 패치를 적용하세요.**

## 변경 파일

### 신규
- `docs/OPERATIONS.md` — 운영 명령어 가이드 (인원수 변경, 데이터 정리, 트러블슈팅)

### 수정
- `README.md`
  - 디렉토리 섹션에 OPERATIONS.md 링크 추가
  - 빠른 시작에 KV config 등록 단계 추가
  - 핵심 설계 원칙에 "도메인 설정 KV 통합 (SSoT)" 추가

- `docs/SETUP.md`
  - 2-3 단계 신규: "도메인 설정 등록 (`config:members_count`)"
  - 후속 섹션 번호 +1 (2-4: 비밀 값, 2-5: 배포, 2-6: Discord, 2-7: 슬래시)
  - 3-4의 Variables 표에서 `MEMBERS_COUNT` 행 제거
  - SSoT 구조 안내 박스 추가

## 적용 방법

```bash
cd ~/workbench/team-claude-billing

unzip -o ~/Downloads/docs_improvement.zip -d /tmp/

cp /tmp/docs_patch/README.md ./
cp /tmp/docs_patch/docs/SETUP.md docs/
cp /tmp/docs_patch/docs/OPERATIONS.md docs/

# 변경 확인
git status
git diff README.md docs/SETUP.md
cat docs/OPERATIONS.md | head -30  # 새 파일 확인

# commit
git add README.md docs/SETUP.md docs/OPERATIONS.md
git commit -m "docs: members_count SSoT 통합 반영 + 운영 가이드 분리"
git push
```

## 검증 체크리스트

- [ ] README의 "빠른 시작"에 KV config 등록 단계가 있는지
- [ ] SETUP.md의 2-3 섹션이 도메인 설정 등록 안내인지
- [ ] SETUP.md의 Variables 표에 MEMBERS_COUNT가 **없는지**
- [ ] OPERATIONS.md가 docs/에 있고 README에서 링크되는지
