# 파사드 / 서비스

계층 의존은 [SKILL.md](SKILL.md) 참조. 여기서는 그 안에서 **무엇을 어디에 둘지**를 다룬다.

## 서비스 분류 — 리소스 단위, 유즈케이스는 메서드

서비스는 **리소스(애그리거트) 단위로 묶고 유즈케이스는 메서드로** 둔다. 유즈케이스마다 클래스를 쪼개지 않는다 — `CreateOrderService`·`CancelOrderService` 식 동사-클래스 분할은 클래스 수만 늘리고 응집을 깬다. 정말 무거운 단일 흐름만 예외.

| 클래스 | 역할 |
|---|---|
| `{Domain}Service` | 그 도메인의 쓰기·도메인 로직. 여러 유즈케이스 = 여러 메서드. 보통 엔티티 반환 |
| `{Domain}QueryService` | 읽기 전용 분리 |
| `Common{Domain}Service` | 여러 Facade/Service 가 **똑같이 써야 하는** 정규 연산 + 타 도메인의 진입점 |
| `{Domain}{Role}Service` | 특정 역할 전용 |

## 로직 배치 — "다르면 버그인가?"

"재사용되나?"로 판단하면 공통 서비스가 잡동사니 통이 된다. 기준은 **"다른 유즈케이스가 이걸 다르게 하면 버그인가?"** 다.

1. 단일 애그리거트의 불변식·상태전이 → **엔티티** (`order.markPaid()`)
2. 모든 유즈케이스가 **동일해야** 하는 정규 연산(정규 조회·공유 검증·다중 애그리거트 규칙) → **`Common{Domain}Service`**
3. 이 유즈케이스 특유의 순서·정책·분기(달라도 정당) → 해당 **`{Domain}Service` 메서드**
4. 애매하면 → 일단 3번. 둘째 유즈케이스가 *동일한* 연산을 요구할 때 승격한다. 미리 올리지 않는다.

이름은 `Common`(공유)이지만 넣는 기준은 **불변·정규**다.

## 트랜잭션

- **Service**: 클래스 레벨 `@Transactional(readOnly = true)` + 쓰기 메서드에 `@Transactional` 오버라이드.
- **Facade**: 클래스 레벨 `@Transactional` **없음**. 메서드별로 지정한다(쓰기 `@Transactional`, 조회 `@Transactional(readOnly = true)`).

인터페이스·추상 클래스·DB 를 쓰지 않는 구현체(캐시·외부 API 어댑터)에는 붙이지 않는다. 붙여도 컴파일은 되지만 의미가 없고 오해를 만든다.

어노테이션 순서: Service 는 `@Service` → `@RequiredArgsConstructor` → `@Transactional(readOnly = true)`. Facade 는 앞의 둘만.

## 메서드 구조

검증 → 엔티티 생성·변경 → 저장. `save`/`saveAll` 은 메서드 하단에.

```java
@Service
@RequiredArgsConstructor
public class ProductAdminFacade {
  private final ProductAdminService productAdminService;
  private final CategoryService categoryService;
  private final ProductMapper productMapper;

  @Transactional
  public CreateProductResponse createProduct(CreateProductRequest request) {
    Category category = categoryService.getCategory(request.categoryId());
    Product product = productAdminService.create(request, category);
    return productMapper.toCreateResponse(product);
  }
}

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductAdminService {
  private final ProductRepository productRepository;

  @Transactional
  public Product create(CreateProductRequest request, Category category) {
    Product product = Product.create(request, category);
    return productRepository.save(product);
  }
}
```

## 검증 메서드는 스스로를 지킨다 — 입력 부재에 한해

검증 메서드가 null/empty 를 **자기 안에서** 처리하면 호출부가 분기 없이 직선으로 흐른다.

```java
// ❌ 호출부 분기
if (options != null && !options.isEmpty()) validateDuplicateNames(options);

// ✅
validateDuplicateNames(options);

private void validateDuplicateNames(List<String> names) {
  if (names == null || names.isEmpty()) return;
  ...
}
```

**적용 한계**: 입력 부재가 "검증할 대상이 없음"을 뜻할 때만이다. null/empty 가 **별개의 비즈니스 분기**를 뜻하면(예: `promotion == null` = 프로모션이 적용되지 않은 주문) 숨기지 말고 드러낸다.

`saveAll(빈 리스트)` 는 에러 없이 통과한다(null 만 거부). 호출부에 `if (list.isEmpty()) skip` 을 두지 않아도 되도록, 호출되는 메서드들도 빈 입력을 안전하게 처리한다.

## 비즈니스 분기는 이름으로 표출

조건부 스킵을 self-guard 로 처리할 때, 이름에는 **코드 조건이 아니라 도메인 의미**를 담는다.

```java
// ❌ null 이라는 코드 사실만 드러남
validateNotExpiredIfNotNull(promotion);

// ✅ "프로모션이 적용된 주문이면 검증"
validateNotExpiredIfPromotion(promotion);
```

- `validate`/`ensure`/`require` 만으로는 "null 이면 통과"가 안 드러난다. 조건부 스킵이면 `IfXxx`(비즈니스 조건) 접미사로 표출한다.
- 조건이 둘 이상 얽히면 이름으로 우기지 말고 호출부 `if` 로 뺀다.
- **정직성 단서**: 비즈니스 이름은 그 조건이 실제로 그 경우와 정확히 일치할 때만 정직하다. `promotion == null` 이 로딩 누락이나 버그일 수 있으면 self-guard 가 아니라 fail-fast(`requireNonNull`)가 맞다.
- 위 계층(Facade/Service)일수록 의도로, 아래(Repository)일수록 메커니즘으로 명명한다.

## 연관 탐색 — 2-hop 체이닝 금지

객체는 직접 이웃하고만 대화한다(디미터). 연관의 id·단순 값이 필요하면 엔티티가 위임 메서드로 노출한다.

- ❌ `order.getProduct().getId()` — Order 가 Product 내부로 들어감
- ✅ `order.getProductId()` — Order 가 `product.getId()` 를 위임

- **1-hop 객체 전달은 정당하다.** `validateNotExpiredIfPromotion(order.getPromotion())` 처럼 직접 이웃을 협력 객체에 넘기는 건 위반이 아니다.
- **응답 DTO 조립은 예외.** MapStruct 중첩 매핑(`@Mapping(source = "user.name", ...)`)은 허용한다. 위임은 도메인 로직의 의미 있는 값에 한정하고, 단순 데이터 추출까지 위임으로 만들면 메서드만 폭발한다.
- 막는 기준은 애그리거트 경계가 아니라 **캡슐화를 깨는 체이닝**이다. 같은 애그리거트 안(`order.getOrderItem().getName()`)에도 똑같이 적용된다.

의존 경계와 체이닝 금지는 **코드 리뷰가 안전장치**다. ArchUnit 같은 자동 강제를 두는 저장소도 있다.
