# 엔티티

## 클래스 선언

```java
@Entity
@Getter
@Builder(access = PRIVATE)
@NoArgsConstructor
@AllArgsConstructor(access = PRIVATE)
@FieldDefaults(level = PRIVATE)
@DynamicInsert
@DynamicUpdate
@Table(name = "products")
public class Product extends BaseEntity {
```

- 공통 부모(`BaseEntity`)가 `id`·`createdAt`·`updatedAt` 을 갖는다. 엔티티마다 다시 선언하지 않는다.
- 생성자·빌더는 `PRIVATE`. 외부 인스턴스화는 정적 팩토리로만.
- 필드는 접근제어자를 생략하고(`@FieldDefaults`) `@Column` 으로 제약을 명시한다(`nullable`/`length`/`precision`).
- 테이블명은 복수형 스네이크. 셀 수 없는 명사는 단수(`stock`).

**필드 순서**: 값·스칼라·enum 을 먼저, **JPA 연관 매핑은 클래스 하단**에 모은다.

## 연관 매핑

```java
@ManyToOne(fetch = LAZY)
@JoinColumn(name = "category_id")
Category category;

@Builder.Default
@OneToMany(mappedBy = "product", cascade = ALL, orphanRemoval = true, fetch = LAZY)
List<ProductOption> options = new ArrayList<>();

@Enumerated(STRING)
@Column(nullable = false, length = 20)
ProductStatus status;
```

- `@ManyToOne` 은 항상 `LAZY`. `@OneToMany` 컬렉션은 `@Builder.Default` 로 빈 리스트 초기화.
- enum 은 `@Enumerated(STRING)` — ordinal 은 순서가 바뀌면 데이터가 깨진다.

> **DB FK 제약을 걸지 않는 저장소가 있다**(`@ForeignKey(ConstraintMode.NO_CONSTRAINT)` + DDL 에도 미선언). 고트래픽 쓰기의 부모 행 잠금 제거나 서비스 분리를 대비한 결정이며, 저장소 CLAUDE.md 와 ADR 을 확인한다.

객체 탐색이 실제로 필요 없고 독립적으로 갱신되는 행은 연관 매핑 없이 FK 값 컬럼(`Long`) + 전용 조회로 두기도 한다. 탐색이 필요하면 평범하게 `@ManyToOne` 으로 매핑한다.

## 정적 팩토리

Request 를 그대로 받고, 외부 연관만 별도 파라미터로 받는다. 조립·검증·자식 생성을 안에서 끝낸다.

```java
public static Product create(CreateProductRequest request, Category category) {
    Product product = Product.builder()
        .name(request.name())
        .price(request.price())
        .status(ProductStatus.FOR_SALE)
        .category(category)
        .build();
    product.validateDuplicateOptionNames(request.optionNames());
    product.createOptions(request.options());
    return product;
}
```

## 도메인 메서드

상태 변경·검증·파생 계산은 전부 엔티티 안에 둔다 (`updateInfo`, `replaceOptions`, `markPaid`, `getOptionOrThrow`).

```java
private void validateDuplicateOptionNames(List<String> names) {
    if (names.size() != Set.copyOf(names).size()) {
        throw new DomainException(DUPLICATE_OPTION_NAME);
    }
}
```

- 예외 코드는 static import 로 짧게 쓴다.
- 연관의 id·값이 외부에 필요하면 **위임 메서드로 노출**한다 — `order.getProduct().getId()` 가 아니라 `order.getProductId()`. 상세는 [service.md](service.md) 의 디미터 절.

## 컬럼 의미 주석

식별자만으로 도메인 의미가 안 드러나는 컬럼은 Hibernate `@Comment("한국어")` 로 명시한다. `ddl-auto: none` 환경에서는 DB 에 반영되지 않으므로 **마이그레이션 DDL 의 `COMMENT` 와 문구를 일치**시킨다.

enum 상수도 각 값의 의미를 `//` 로 한 줄 단다.

```java
public enum PaymentStatus {
    PENDING,    // 결제 대기
    CONFIRMED,  // 승인 완료
    CANCELED,   // 취소
}
```

공통 부모 컬럼과 자명한 컬럼은 생략한다. 이것은 "주석 최소" 원칙의 **엔티티·enum 한정 예외**다 — 컬럼과 상태의 의미는 운영·리뷰에서 실제로 필요하다.

## 논리 삭제

공통 부모에 논리삭제 필드를 넣지 않는다. 필요한 도메인만 개별로 `isDeleted` + `markDeleted()` 를 둔다. 대부분은 상태 enum(`STOP_SALE` 등)으로 노출을 제어하는 편이 낫다.
