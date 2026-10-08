from django.db import models


class Product(models.Model):
    # 1. Main product data
    title = models.CharField(max_length=500, null=True, blank=True)
    product_code = models.CharField(max_length=100, null=True, blank=True)
    vendor = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField(max_length=100, null=True, blank=True)
    memory_capacity = models.CharField(max_length=100, null=True, blank=True)
    regular_price = models.CharField(max_length=100, null=True, blank=True)
    promo_price = models.CharField(max_length=100, null=True, blank=True)

    # 2. Specifications and Media
    screen_diagonal = models.CharField(max_length=100, null=True, blank=True)
    display_resolution = models.CharField(max_length=100, null=True, blank=True)
    reviews_count = models.CharField(max_length=100, null=True, blank=True)
    photos = models.JSONField(default=list, null=True, blank=True)
    specifications = models.JSONField(default=dict, null=True, blank=True)

    # 3. Service fields
    link = models.URLField(max_length=1000, null=True, blank=True)
    parser_type = models.CharField(max_length=50, null=True, blank=True)  # bs4, selenium, playwright
    status = models.CharField(max_length=50, default="New", null=True, blank=True)

    def __str__(self):
        return f"{self.title or 'Product'} ({self.parser_type})"