from django.db import models
from django.db.models import F


class Category(models.Model):
    """10 danh mục sản phẩm của hệ thống."""
    BOOK        = 'book'
    PHONE       = 'phone'
    LAPTOP      = 'laptop'
    TABLET      = 'tablet'
    FASHION     = 'fashion'
    APPLIANCE   = 'appliance'
    COSMETICS   = 'cosmetics'
    FOOD        = 'food'
    TOY         = 'toy'
    SPORT       = 'sport'

    CATEGORY_CHOICES = [
        (BOOK,      'Sách'),
        (PHONE,     'Điện thoại'),
        (LAPTOP,    'Laptop'),
        (TABLET,    'Máy tính bảng'),
        (FASHION,   'Thời trang'),
        (APPLIANCE, 'Gia dụng'),
        (COSMETICS, 'Mỹ phẩm'),
        (FOOD,      'Thực phẩm'),
        (TOY,       'Đồ chơi'),
        (SPORT,     'Thể thao'),
    ]

    slug        = models.CharField(max_length=50, choices=CATEGORY_CHOICES, unique=True, primary_key=True)
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=50, blank=True, help_text="CSS icon class hoặc emoji")

    def __str__(self):
        return self.name

    class Meta:
        db_table  = 'categories'
        verbose_name_plural = 'categories'


class Product(models.Model):
    """
    Model sản phẩm dùng kiến trúc Single-Table-Inheritance + JSONB.
    Trường `attributes` lưu các thuộc tính đặc thù của từng loại sản phẩm.
    VD: Book → {author, isbn, publisher, pages}
        Phone → {brand, ram, storage, battery}
        Fashion → {size, color, material, gender}
    Không dùng Foreign Key sang bất kỳ service nào khác.
    """
    name        = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=12, decimal_places=2)
    stock       = models.PositiveIntegerField(default=0)
    category    = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        db_column='category_slug'
    )
    # JSONB field — lưu thuộc tính đa hình của 10 loại SP
    attributes  = models.JSONField(default=dict, blank=True,
                                   help_text="Thuộc tính đặc thù theo category (JSON)")
    image_url   = models.URLField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # Optimistic Locking — version counter
    version     = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"[{self.category_id}] {self.name}"

    def update_stock(self, delta: int, expected_version: int) -> bool:
        """
        Cập nhật tồn kho với Optimistic Locking.
        Trả về True nếu thành công, False nếu version đã thay đổi (conflict).
        """
        updated = Product.objects.filter(
            pk=self.pk,
            version=expected_version,
            stock__gte=-delta if delta < 0 else 0
        ).update(
            stock=F('stock') + delta,
            version=F('version') + 1
        )
        return updated == 1

    class Meta:
        db_table = 'products'
        indexes  = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['name']),
        ]
