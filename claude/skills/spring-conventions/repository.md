# Repository

```java
public interface ProductRepository extends JpaRepository<Product, Long>, ProductRepositoryCustom {
}
```

QueryDSL 동적 쿼리가 필요하면 `{Domain}RepositoryCustom` 을 함께 상속한다 → [querydsl.md](querydsl.md).

## derived query vs @Query

**조건 1~2개면 derived query.** `existsByCategoryId`, `findByExternalProductId`.

**fetch join·복잡 조건·명시적 쿼리는 `@Query` JPQL.** text block 으로 쓰면 읽힌다.

```java
@Query("""
    SELECT p FROM Product p
    LEFT JOIN FETCH p.options
    LEFT JOIN FETCH p.category
    WHERE p.id = :productId AND p.status = 'FOR_SALE'
""")
Optional<Product> findByIdWithOptionsAndCategory(@Param("productId") Long productId);
```

조건이 늘어날수록 derived query 의 메서드명이 읽을 수 없게 길어진다. 그 지점이 `@Query` + 의미 있는 이름으로 갈아탈 시점이다.

## 관례

- **`>= 1` 만 확인하는 카운팅은 `exists`.** DB 가 limit 1 로 끝내고 의도도 직접적이다.
- **상태·고정 분류는 쿼리 안에 박는다.** `status = 'FOR_SALE'` 을 파라미터로 빼면 호출부마다 같은 상수를 넘기게 된다.
- **반환은 `Optional`.** null 을 반환하지 않는다.
- 조건부 UPDATE 로 동시성을 처리하는 경우, 갱신 행 수를 반환받아 성공 여부를 판정한다.

```java
@Modifying
@Query("""
    UPDATE ProductStock ps
       SET ps.reservedQuantity = ps.reservedQuantity + :quantity
     WHERE ps.productId = :productId
       AND ps.onHandQuantity - ps.reservedQuantity >= :quantity
""")
int reserve(@Param("productId") Long productId, @Param("quantity") int quantity);
```

`0` 이면 재고 부족이다. 조회 후 검사하고 저장하는 방식(read-modify-write)은 동시 요청에서 초과 판매를 만든다.

## 대량 처리 경로

대량 upsert 나 성능이 중요한 경로는 JPA 를 우회해 별도 JDBC 리포지토리를 둔다(`{Domain}JdbcRepository`, `JdbcTemplate` native). 영속성 컨텍스트를 태우지 않으므로 flush·dirty checking 비용이 없다.

이건 성능 문제가 실제로 측정된 뒤에 도입한다. 미리 만들지 않는다.
