# DTO

`dto/request/`, `dto/response/` 에 두고 **record** 로 작성한다.

## Request — record + Bean Validation

```java
public record CreateProductRequest(
    @NotBlank @Size(max = 100) String name,
    String description,
    @NotNull @DecimalMin("0") BigDecimal price,
    @NotNull @Min(0) Integer stock,
    @NotNull Long categoryId,
    @Valid List<ProductOption> options
) {
    public CreateProductRequest {
        options = options != null ? options : List.of();
    }

    public record ProductOption(
        @NotBlank String name,
        @NotNull @DecimalMin("0") BigDecimal additionalPrice,
        @NotNull @Min(0) Integer stock
    ) {}
}
```

- 단순 입력 검증은 전부 어노테이션으로 — `@NotNull`/`@NotBlank`/`@Size`/`@Min`/`@DecimalMin`/`@Pattern`/`@Email`/`@Future`. 전역 예외 핸들러가 400 으로 변환한다.
- 기본값은 **compact constructor** 에서. 별도 팩토리나 빌더를 만들지 않는다.
- 중첩 컬렉션에는 `@Valid` 를 붙여야 안쪽까지 검증된다. 빠뜨리기 쉽다.
- 중첩 타입은 바깥 record 안에 inner record 로.

**비즈니스 룰은 DTO 에 넣지 않는다.** 상태 의존이나 조회가 필요한 검증은 엔티티·서비스에서 도메인 예외로 던진다.

## Response — record + MapStruct

```java
public record CreateProductResponse(Long productId) {}

@Mapper(componentModel = "spring")
public interface ProductMapper {
    @Mapping(source = "id", target = "productId")
    CreateProductResponse toCreateResponse(Product product);

    ProductDetailResponse toDetailResponse(Product product);
    ProductDetailResponse.OptionInfo toOptionInfo(ProductOption option);
}
```

- 엔티티 → Response 변환은 손으로 쓰지 않고 MapStruct 매퍼에 맡긴다.
- 이름이 다른 필드만 `@Mapping` 으로 연결한다. 같은 이름은 자동 매핑된다.
- 중첩 Response 는 inner record.
- QueryDSL 로 직접 뽑는 Response 는 `@QueryProjection` 생성자를 단다 → [querydsl.md](querydsl.md).

## 페이지 응답

`Page<T>` 를 그대로 직렬화하면 Spring 내부 구조가 API 계약으로 새어나간다. 전용 envelope 를 둔다.

```java
public record ProductPageEnvelope(
    List<ProductListResponse> content, int page, int size, long totalElements, int totalPages
) {
    public static ProductPageEnvelope from(Page<ProductListResponse> page) { ... }
}
```

## 네이밍

- Request: `{Action}{Domain}Request` — `CreateProductRequest`, `UpdateProductRequest`
- Response: `{Action}{Domain}Response` 또는 `{Domain}{용도}Response` — `CreateProductResponse`, `ProductDetailResponse`, `CouponListItemResponse`

## Command 재매핑을 하지 않는다

인바운드 입구가 REST 하나뿐이면 Request 를 별도 command 객체로 다시 매핑하지 않는다. 대부분 필드가 같은 복사본이 되고 Bean Validation 이 두 곳으로 갈린다.

입구가 둘 이상이 될 때(같은 Facade 메서드를 메시지 컨슈머도 호출) 그때 도입한다.
