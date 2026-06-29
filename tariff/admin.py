from django.contrib import admin
from .models import TariffCode

@admin.register(TariffCode)
class TariffCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'text_fr', 'breadcrumb_fr')  
    search_fields = ('code', 'text_fr', 'text_de', 'breadcrumb_fr')
    list_filter = ('valid_from',)