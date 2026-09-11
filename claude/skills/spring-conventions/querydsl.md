# QueryDSL

구현은 `{Domain}RepositoryCustomImpl` 에 둔다.

```java
import static ...product.entity.QProduct.product;

@RequiredArgsConstructor
public class ProductRepositoryCustomImpl implements ProductRepositoryCustom {
  private final JPAQueryFactory queryFactory;
}
```

`JPAQueryFactory` 는 설정 클래스에서 빈으로 등록해 주입받는다. Q클래스는 static import 로 짧게.

## 동적 조건 — null 을 반환하는 private BooleanExpression

`where(...)` 에 넘긴 인자가 `null` 이면 그 조건은 자동으로 빠진다. 이 성질을 이용해 조건마다 메서드를 분리한다.

```java
.where(
    product.status.eq(ProductStatus.FOR_SALE),
    keywordContains(request.keyword()),
    priceGoe(request.minPrice()),
    categoryMatch(searchCategory)
)

private BooleanExpression keywordContains(String keyword) {
  return keyword != null ? product.name.containsIgnoreCase(keyword) : null;
}
```

`BooleanBuilder` + `if` 누적보다 읽기 쉽고, 조건 하나가 메서드 하나라 재사용·테스트가 된다.

**DB 벤더 전용 함수를 쓰지 않는다** — Hibernate 버전이나 DB 를 바꿀 때 조용히 깨진다.

## 프로젝션

DTO 를 직접 select 할 때는 `@QueryProjection` 생성자 record 의 Q타입을 쓴다.

```java
public record ProductListResponse(Long id, String name, BigDecimal price) {
  @QueryProjection
  public ProductListResponse { }
}

.select(new QProductListResponse(product.id, product.name, product.price))
```

컴파일 타임에 필드가 검증된다. `Projections.fields`/`bean` 은 이름이 어긋나도 컴파일이 통과하고 런타임에 null 이 들어온다.

## 페이징

```java
List<ProductListResponse> content = queryFactory
    .select(...).from(product)
    .where(조건들)
    .orderBy(getOrderSpecifier(pageable))
    .offset(pageable.getOffset())
    .limit(pageable.getPageSize())
    .fetch();

JPAQuery<Long> countQuery = queryFactory
    .select(product.count()).from(product)
    .where(조건들);

return PageableExecutionUtils.getPage(content, pageable, countQuery::fetchOne);
```

- `countQuery::fetchOne` 은 **메서드 참조**여야 한다. 마지막 페이지이거나 결과가 페이지 크기보다 작으면 count 쿼리를 아예 실행하지 않는다. `.fetchOne()` 을 바로 호출하면 이 최적화가 사라진다.
- **content 와 count 의 `where` 조건은 같아야 한다.** 다르면 총 개수가 틀린다. 조건을 변수로 뽑아 양쪽에 넘기는 편이 안전하다.

## 정렬

`Pageable` 의 sort 를 `OrderSpecifier` 로 매핑하고, **기본 정렬을 반드시 명시**한다(`product.createdAt.desc()`). 정렬이 없으면 DB 가 순서를 보장하지 않아 페이지 사이에 행이 중복되거나 누락된다.
