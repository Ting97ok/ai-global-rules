# 통합 테스트

```java
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@WithMockUser(roles = "ADMIN")
@DisplayName("카테고리 등록 API")
class CreateCategoryIntegrationTest {

  @Autowired MockMvc mockMvc;
  @Autowired ObjectMapper objectMapper;
  @Autowired CategoryRepository categoryRepository;
}
```

**어노테이션 네 개가 한 세트다.** 특히 `@ActiveProfiles("test")` 를 빠뜨리면 테스트 전용 DB 설정이 안 잡히고, 원인이 로그에 직접 드러나지 않는다.

**공통 베이스 클래스를 만들지 어떨지는 저장소마다 다르다.** 없는 저장소에서 "빠진 것"으로 오해하고 새로 만들지 않는다 — 각 테스트가 어노테이션을 직접 다는 것이 의도인 경우가 많다. 기존 테스트를 먼저 본다.

## 인프라

testcontainers 로 실제 DB·Redis 를 띄우는 저장소가 많다. 그러면:

- **테스트 실행에 Docker 가 필요하다.** 컨테이너가 못 뜨면 애플리케이션 로딩부터 실패하는데, 스택 트레이스만 보면 코드 버그처럼 보인다. 테스트가 무더기로 깨지면 Docker 부터 확인한다.
- 마이그레이션(Flyway 등)이 운영과 동일하게 실행되므로 **DDL 방언까지 테스트에서 검증된다**. 이것이 in-memory DB 대신 쓰는 이유다.
- **이미 적용된 마이그레이션 파일을 수정하면 체크섬이 어긋나 전체 테스트가 죽는다.** 스키마 변경은 항상 새 버전 파일을 추가한다.

인증은 `@WithMockUser(roles = "...")` 로 처리하고 토큰을 직접 만들지 않는다. 공개 API 테스트에서는 생략한다.

## 구조 · 격리

- `@Nested` + `@DisplayName` 으로 성공/실패 그룹을 나눈다. `@DisplayName` 은 시나리오를 서술하고, 메서드명은 영어 camelCase.
- 격리는 `@BeforeEach` 의 `repository.deleteAll()`.
- **클래스 레벨 `@Transactional` 을 붙이지 않는다.** 붙이면 테스트 트랜잭션이 롤백되면서, `mockMvc.perform` 이 별도 트랜잭션으로 커밋한 결과를 repository 로 검증하는 흐름이 깨진다.

## 단언

```java
mockMvc.perform(post("/api/admin/categories").contentType(APPLICATION_JSON).content(...))
    .andExpect(status().isOk())
    .andExpect(jsonPath("$.result").value(true))
    .andExpect(jsonPath("$.data.categoryId").isNumber());
```

**응답 봉투가 있으면 단언 경로가 한 단계 깊어진다** — `$.categoryId` 가 아니라 `$.data.categoryId`. 컨트롤러가 raw DTO 를 반환한다는 사실만 보고 단언을 쓰면 여기서 틀린다. → [controller.md](controller.md)

실패는 예외 코드 이름으로 단언한다(`$.error.code == "CATEGORY_NOT_FOUND"`). 메시지 문자열로 단언하면 문구를 다듬을 때마다 테스트가 깨진다.

- Bean Validation 실패 → 400
- 비즈니스 검증 실패 → 도메인 예외가 지정한 상태(404/400/409 …)

## 외부 시스템

외부 PG·API 는 `@MockBean` 이나 가짜 대역으로 차단한다. 실제로 호출하면 테스트가 네트워크와 상대 서비스 상태에 의존하게 된다.

## given/when/then 주석

`// given` 같은 마커 주석을 달지 않는다. 빈 줄과 메서드 구조로 구분한다.
