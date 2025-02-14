from rest_framework.pagination import PageNumberPagination

class AdminPageNumberPagination(PageNumberPagination):
    page_size = 10  # You can change this to fit your UI
    page_size_query_param = 'page_size'
    max_page_size = 100
