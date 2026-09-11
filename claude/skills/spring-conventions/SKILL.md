---
name: spring-conventions
description: Spring Boot + JPA 프로젝트에서 Java 코드를 작성·수정하기 전에 읽는다. 엔티티 매핑, record DTO + Bean Validation, MapStruct, Repository/QueryDSL, Facade/Service 계층 배치, 트랜잭션 경계, 통합 테스트의 코드 예제를 담는다. 'JPA 엔티티 만들어줘', '이 DTO 검증 추가', 'QueryDSL 페이징', '서비스 계층 어디에 둬야 하나', '통합 테스트 작성' 같은 작업에서 사용.
---

# Spring Boot 코딩 컨벤션

Spring Boot 3.x + Java 21 + JPA/QueryDSL 프로젝트의 재사용 가능한 코드 패턴 모음이다.

**이 스킬은 일반 패턴만 담는다.** 저장소마다 다른 결정(계층 개수, FK 제약 사용 여부, 응답 래핑 방식, DB 벤더, 들여쓰기)은 **해당 저장소의 CLAUDE.md 가 정본**이며, 충돌하면 저장소 쪽이 이긴다.

## 계층 의존

```
Controller → Facade → Service → Repository
                      entity | dto | mapper | exception
```

- Controller 는 Facade 만 호출한다.
- Facade 는 타 도메인 Service 를 호출할 수 있다. Repository 직접 호출은 하지 않는다. cross-domain 조정 + Response 조립 담당.
- Service 는 자기 도메인 Repository + 같은 도메인 공통 Service 만 의존한다. 타 도메인 Service 를 직접 부르지 않고 Facade 를 경유한다. 보통 엔티티를 반환한다.

Facade 계층을 두지 않는 저장소도 있다(3계층). 어느 쪽인지는 저장소 CLAUDE.md 를 따른다.

## 참조 파일

작업 중인 계층의 파일만 읽는다.

| 파일 | 담는 것 |
|---|---|
| [entity.md](entity.md) | 어노테이션 세트, 정적 팩토리, 연관 매핑, 도메인 메서드 |
| [dto.md](dto.md) | record Request/Response, Bean Validation, MapStruct |
| [controller.md](controller.md) | 선언 골격, URL·파라미터, 페이지 응답 |
| [service.md](service.md) | 서비스 분류, 로직 배치 기준, 트랜잭션, 네이밍, 디미터 |
| [repository.md](repository.md) | derived query vs @Query, fetch join, JDBC 경로 |
| [querydsl.md](querydsl.md) | 동적 조건, 프로젝션, 페이징, 정렬 |
| [test.md](test.md) | 통합 테스트 구조, 격리, 단언 |

## 공통 원칙

- **검증은 Bean Validation 우선.** 필수·길이·형식·부호·날짜는 record 필드 어노테이션으로. 상태 의존이나 Repository 조회가 필요한 비즈니스 룰만 엔티티·서비스에서 예외를 던진다.
- **엔티티는 rich.** 상태 변경·불변식·파생 계산을 도메인 메서드로 캡슐화한다. 서비스가 setter 로 조립하지 않는다.
- **예외는 도메인 enum.** `IllegalStateException`/`IllegalArgumentException` 같은 범용 예외를 남발하지 않는다. 저장소의 예외 체계를 따른다.
- **주석은 최소.** 의미는 이름·타입·구조로 드러낸다. 무엇을 하는지(what) 설명하는 주석과 Javadoc 은 쓰지 않는다. 이름으로 안 되는 복잡한 로직에만 왜(why) 를 한 줄.

**출력 언어**: 한국어 (예외 — 코드 식별자, 외부 인용은 원문 유지)
