# 컨트롤러

```java
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/admin/products")
public class ProductAdminController {

  private final ProductAdminFacade productAdminFacade;

  @PostMapping
  public CreateProductResponse createProduct(@RequestBody @Valid CreateProductRequest request) {
    return productAdminFacade.createProduct(request);
  }
}
```

- 필드 주입(`@Autowired`)이 아니라 `@RequiredArgsConstructor` + `final`.
- 컨트롤러는 Facade 만 부른다. 분기·조회·조립을 여기서 하지 않는다.
- 클래스명은 `{Domain}{Role}Controller` 또는 `{Role}{Domain}Controller`. 저장소 안에서만 일관되면 된다.

## 응답 래핑

전역 `ResponseBodyAdvice` 로 `{result, data, error}` 같은 공통 봉투를 씌우는 저장소가 많다. **그런 저장소에서는 컨트롤러가 raw DTO 를 반환하고, 직접 감싸면 이중 래핑이 된다.**

씌우는지 아닌지는 저장소 CLAUDE.md 와 `global/response/` 를 확인한다. 이 판단을 틀리면 응답 구조가 통째로 어긋나고 **테스트 단언 경로까지 같이 틀어진다**(`$.data.productId` vs `$.productId`).

실패 응답은 전역 예외 핸들러가 만든다. 컨트롤러에 try-catch 를 두지 않는다.

## URL · 파라미터

- 관리자 API `/api/admin/{resource}`, 사용자 API `/api/{resource}`.
- 쓰기: `@RequestBody @Valid {record}`.
- 검색: `@Valid {record}` + `@PageableDefault(sort = "createdAt", direction = DESC) Pageable`.
- 식별자: `@PathVariable Long {id}`.
- 페이지 조회는 envelope 로 반환 → [dto.md](dto.md).

## 인증

인증 사용자 정보는 커스텀 ArgumentResolver 로 받는다(`@CurrentUser CurrentUser currentUser`). 비회원 접근이 가능한 엔드포인트에서는 `null` 이 올 수 있으므로 그 분기를 드러낸다.

권한은 Spring Security role 로 처리하고 컨트롤러 본문에서 손으로 검사하지 않는다.

## Swagger

컨트롤러에 `@Tag`/`@Operation` 을 다는 저장소와 springdoc 자동 문서화에만 의존하는 저장소가 갈린다. 기존 컨트롤러가 안 달고 있으면 새 컨트롤러에도 달지 않는다.
