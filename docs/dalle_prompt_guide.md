# DALL-E 3 이미지 프롬프트 가이드

## 기본 스타일 (모든 이미지 공통 적용)

```
flat design illustration, pure black background (#000000),
vibrant colorful objects, clean and simple composition,
no text, no letters, no numbers, no words
```

---

## 프롬프트 구조

```
[장면 묘사] + , + [기본 스타일]
```

**장면 묘사 작성 원칙:**
- 해당 세그먼트 나레이션의 핵심 개념을 시각적 오브젝트로 표현
- 추상적 개념 → 구체적 사물로 치환
- 동작/상태 포함 (rising, falling, connected, locked 등)
- 2~4개 핵심 오브젝트로 구성

---

## 경제 개념별 시각화 사전

| 개념 | 시각화 오브젝트 |
|------|----------------|
| 금리 상승 | upward arrow with coins stacked, bank building |
| 금리 하락 | downward arrow with coins, piggy bank |
| 인플레이션 | shopping cart overflowing, price tag with rising arrow |
| 주식 상승 | colorful bar chart going up, rocket with dollar sign |
| 주식 하락 | red bar chart going down, falling coins |
| 부동산 | house with price tag, magnifying glass over land |
| 채권 | document with seal, clock with interest symbol |
| 중앙은행 | large bank building with gear mechanism |
| GDP | globe with factory, city buildings, dollar flow |
| 환율 | two currency symbols exchanging arrows |
| 복리 | exponentially growing money tree |
| 분산투자 | multiple baskets each with different colored eggs |
| 세금 | government building receiving coins from people |
| 대출/부채 | person with heavy chain attached to debt bag |
| 펀드/ETF | basket of mixed colorful stocks and bonds |
| 경기침체 | empty street with closed shop signs |
| 경기 호황 | busy city with upward arrows everywhere |
| 양적완화 | printing press outputting money bills |
| 무역 | cargo ship with shipping containers, globe |
| 공급/수요 | two opposing arrows with goods in middle |

---

## 세그먼트별 프롬프트 패턴

### 세그먼트 0 — 도입 (호기심 유발)
> 주제를 상징하는 오브젝트를 중앙에 크게, 물음표나 돋보기와 함께

```
[핵심 오브젝트] with glowing spotlight in center, question mark floating nearby,
flat design illustration, pure black background, vibrant colors, no text
```

### 세그먼트 1 — 핵심 개념
> 개념의 작동 원리를 화살표·흐름으로 표현

```
[개념 오브젝트 A] and [오브젝트 B] connected by flowing arrows showing [관계],
flat design illustration, pure black background, vibrant colors, no text
```

### 세그먼트 2 — 실생활 예시/수치
> 일상 사물과 경제 오브젝트를 함께 배치

```
[일상 오브젝트] next to [경제 오브젝트] showing [상황],
flat design illustration, pure black background, vibrant colors, no text
```

### 세그먼트 3 — 정리
> 핵심 결론을 체크마크나 요약 아이콘으로 표현

```
[전체 주제 상징 오브젝트] with checkmark and upward trend,
flat design illustration, pure black background, vibrant colors, no text
```

---

## 실제 예시 — '금리란 무엇인가'

| 세그먼트 | 나레이션 | DALL-E 프롬프트 |
|----------|----------|-----------------|
| 0 | 돈을 빌리면 왜 더 갚아야 할까요? | `coins with plus sign and clock, question mark floating, glowing spotlight, flat design illustration, pure black background, vibrant colors, no text` |
| 1 | 금리는 돈을 빌리는 비용입니다. 은행은 돈을 빌려주고 이자를 받아요. | `bank building with arrow pointing to person holding money bag with percentage symbol attached, flat design illustration, pure black background, vibrant colors, no text` |
| 2 | 금리가 5%라면 100만원을 빌릴 때 1년 후 105만원을 갚아야 해요. | `stack of coins labeled 100 with small growing arrow adding 5 more coins on top, calendar nearby, flat design illustration, pure black background, vibrant colors, no text` |
| 3 | 금리는 경제 전체의 속도를 조절하는 핵심 도구입니다. | `large dial or lever controlling speed of cityscape with gears, flat design illustration, pure black background, vibrant colors, no text` |

---

## Claude에게 전달하는 지시문 (script_generator.py 내 사용)

```
[DALL-E 프롬프트 작성 규칙]
- 해당 세그먼트 나레이션 내용과 직접 연관된 장면 묘사 (영어)
- 아래 고정 스타일을 반드시 끝에 추가:
  "flat design illustration, pure black background (#000000), vibrant colorful objects, clean and simple, no text, no letters, no numbers"
- 나레이션의 핵심 단어를 시각적 오브젝트로 치환
  예) "금리가 오르면" → "upward arrow with percentage sign and stacked coins"
  예) "집을 담보로" → "house with chain and padlock attached to money bag"
  예) "주식이란" → "colorful rising bar chart with dollar signs floating up"
- 오브젝트 2~4개로 구성, 동작/상태 묘사 포함
- 세그먼트 0(도입): 중앙 오브젝트 + question mark
- 세그먼트 3(정리): 오브젝트 + checkmark or upward trend
```
