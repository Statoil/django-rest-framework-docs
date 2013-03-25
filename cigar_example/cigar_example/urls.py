from django.conf.urls import patterns, include

urlpatterns = patterns('',
    (r'^api/v2/', include('cigar_example.restapi.urls')),
    (r'', include('cigar_example.app.urls')),
)
