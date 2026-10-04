from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Profile(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    goal=models.CharField(max_length=120,default='UPSC CSE')
    daily_new_limit=models.PositiveIntegerField(default=20)
    daily_review_limit=models.PositiveIntegerField(default=100)

class Topic(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='topics')
    subject=models.CharField(max_length=80)
    name=models.CharField(max_length=200)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: unique_together=('user','subject','name')

class Source(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='sources')
    topic=models.ForeignKey(Topic,on_delete=models.CASCADE,related_name='sources',null=True,blank=True)
    title=models.CharField(max_length=300)
    file_name=models.CharField(max_length=300,blank=True)
    source_type=models.CharField(max_length=30,default='notes')
    text=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)

class Card(models.Model):
    STATES=[('new','New'),('learning','Learning'),('review','Review'),('relearning','Relearning')]
    TYPES=[('basic','Basic Recall'),('cloze','Cloze'),('reverse','Reverse'),('compare','Compare'),('sequence','Sequence'),('multi','Multi-point'),('pyq','PYQ Recall'),('mains','Mains Recall')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='cards')
    topic=models.ForeignKey(Topic,on_delete=models.SET_NULL,null=True,blank=True,related_name='cards')
    source=models.ForeignKey(Source,on_delete=models.SET_NULL,null=True,blank=True,related_name='cards')
    card_type=models.CharField(max_length=20,choices=TYPES,default='basic')
    prompt=models.TextField(); answer=models.TextField()
    line_start=models.PositiveIntegerField(null=True,blank=True); line_end=models.PositiveIntegerField(null=True,blank=True)
    excerpt=models.TextField(blank=True)
    state=models.CharField(max_length=20,choices=STATES,default='new')
    learning_step=models.PositiveIntegerField(default=0)
    interval_days=models.FloatField(default=0)
    due_at=models.DateTimeField(default=timezone.now)
    reps=models.PositiveIntegerField(default=0); lapses=models.PositiveIntegerField(default=0); ease=models.FloatField(default=2.5)
    last_reviewed=models.DateTimeField(null=True,blank=True); last_rating=models.CharField(max_length=10,blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)

class ReviewLog(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='reviews')
    card=models.ForeignKey(Card,on_delete=models.CASCADE,related_name='reviews')
    rating=models.CharField(max_length=10); from_state=models.CharField(max_length=20); to_state=models.CharField(max_length=20)
    response_ms=models.PositiveIntegerField(default=0); scheduled_at=models.DateTimeField(); created_at=models.DateTimeField(auto_now_add=True)

class PYQ(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='pyqs')
    year=models.PositiveIntegerField(); exam=models.CharField(max_length=50,default='UPSC CSE')
    paper=models.CharField(max_length=50,default='Prelims'); question=models.TextField(); answer=models.TextField(blank=True)
    subject=models.CharField(max_length=80); topic=models.ForeignKey(Topic,on_delete=models.SET_NULL,null=True,blank=True)

class MainsSubmission(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='mains_submissions')
    question=models.TextField(); answer=models.TextField(); marks=models.FloatField(default=0); max_marks=models.PositiveIntegerField(default=10)
    evaluation=models.JSONField(default=dict); created_at=models.DateTimeField(auto_now_add=True)

class MemoryItem(models.Model):
    TYPES=[('intro','Introduction'),('example','Example'),('case','Case/Committee'),('keyword','Keyword'),('conclusion','Conclusion')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='memory_items')
    item_type=models.CharField(max_length=20,choices=TYPES,default='keyword')
    text=models.TextField()
    source_submission=models.ForeignKey('MainsSubmission',on_delete=models.SET_NULL,null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class KnowledgePoint(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='knowledge_points')
    topic=models.ForeignKey(Topic,on_delete=models.CASCADE,related_name='knowledge_points')
    title=models.CharField(max_length=300); body=models.TextField(blank=True)
    source=models.ForeignKey(Source,on_delete=models.SET_NULL,null=True,blank=True)
