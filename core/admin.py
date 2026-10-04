from django.contrib import admin
from .models import *
admin.site.register([Profile,Topic,Source,Card,ReviewLog,PYQ,MainsSubmission,MemoryItem,KnowledgePoint])
