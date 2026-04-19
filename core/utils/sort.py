from rest_framework.filters import OrderingFilter
from rest_framework.exceptions import ValidationError
from django.db.models.functions import Lower
from django.db import models
from django.db.models import F

def apply_sorting(request, queryset, view_class):
    sort_filter = MultiFieldSortFunction()
    ordering = sort_filter.get_ordering(request, queryset, view_class)
    if ordering:
        return queryset.order_by(*ordering)
    return queryset


class MultiFieldSortFunction(OrderingFilter):
    ordering_param = 'sort'

    def get_ordering(self, request, queryset, view):
        sort_param = request.query_params.get(self.ordering_param)
        if not sort_param:
            return getattr(view, 'ordering', None)
        
        raw_fields = [f.strip() for f in sort_param.split(',') if f.strip()]
        if not raw_fields:
            return getattr(view, 'ordering', None)
        
        mapping = getattr(view, 'SORT_MAPPING', {})
        allowed_fields = getattr(view, 'ordering_fields', [])
        annotated_fields = getattr(view, 'annotated_fields', [])

        base_model = queryset.model
        ordering = []

        for field in raw_fields:
            descending = field.startswith("-")
            field_name = field.lstrip("-")

            db_field = mapping.get(field_name, field_name)

            if db_field not in allowed_fields:
                raise ValidationError(f"Sorting by '{field_name}' is not allowed.")
            
            model = base_model
            if db_field in annotated_fields:
                expr=F(db_field)
            else:
                parts = db_field.split("__")
                for part in parts[:-1]:
                    field_obj = model._meta.get_field(part)
                    model = field_obj.remote_field.model

                final_field = parts[-1]
                model_field = model._meta.get_field(final_field)
                
                if isinstance(model_field, (models.CharField, models.TextField)):
                    expr = Lower(db_field)
                else:
                    expr = F(db_field)

            ordering.append(expr.desc() if descending else expr.asc())

        return ordering or getattr(view, "ordering", None)
