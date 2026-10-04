from django.shortcuts import render
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count,Avg
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import *
from .services import extract_file,generate_cards,schedule,evaluate_mains,generate_model_answer

@ensure_csrf_cookie
def spa(request): return render(request,'index.html',{'registration_enabled':settings.ALLOW_PUBLIC_REGISTRATION})

def serialize_card(c):
    return {'id':c.id,'topic':c.topic.name if c.topic else 'Unsorted','topic_id':c.topic_id,'subject':c.topic.subject if c.topic else '', 'type':c.card_type,'q':c.prompt,'a':c.answer,'state':c.state,'due_at':c.due_at.isoformat(),'interval':c.interval_days,'ease':c.ease,'reps':c.reps,'lapses':c.lapses,'source':{'title':c.source.title if c.source else '', 'lineStart':c.line_start,'lineEnd':c.line_end,'excerpt':c.excerpt}}

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request): return Response({'service':'upscEasy','status':'online','api':'v2','message':'Use POST /api/cards/generate/ to generate cards.'})

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    u=authenticate(username=request.data.get('username',''),password=request.data.get('password',''))
    if not u: return Response({'error':'Invalid username or password'},status=400)
    login(request,u); return Response({'user':u.username})

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_register(request):
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        return Response({'error':'New registrations are disabled.'},status=403)
    username=request.data.get('username','').strip(); password=request.data.get('password','')
    if len(username)<3 or len(password)<6: return Response({'error':'Username >=3 chars and password >=6 chars required'},status=400)
    if User.objects.filter(username=username).exists(): return Response({'error':'Username already exists'},status=400)
    u=User.objects.create_user(username=username,password=password); Profile.objects.create(user=u); login(request,u); return Response({'user':u.username},status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request): logout(request); return Response({'ok':True})

@api_view(['GET'])
@permission_classes([AllowAny])
def auth_me(request): return Response({'authenticated':request.user.is_authenticated,'username':request.user.username if request.user.is_authenticated else None})

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def topics(request):
    if request.method=='POST':
        s=request.data.get('subject','').strip(); n=request.data.get('name','').strip()
        if not s or not n:return Response({'error':'subject and name required'},status=400)
        t,_=Topic.objects.get_or_create(user=request.user,subject=s,name=n); return Response({'id':t.id,'subject':t.subject,'name':t.name})
    return Response([{'id':t.id,'subject':t.subject,'name':t.name,'cards':t.cards.count(),'sources':t.sources.count()} for t in request.user.topics.all().order_by('subject','name')])

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def sources(request):
    if request.method=='POST':
        title=request.data.get('title','').strip(); topic_id=request.data.get('topic_id'); text=request.data.get('text',''); upload=request.FILES.get('file')
        typ='notes'
        if upload: text,typ=extract_file(upload)
        if not title: title=upload.name if upload else 'Untitled notes'
        topic=Topic.objects.filter(id=topic_id,user=request.user).first() if topic_id else None
        src=Source.objects.create(user=request.user,topic=topic,title=title,file_name=upload.name if upload else '',source_type=typ,text=text)
        return Response({'id':src.id,'title':src.title,'type':src.source_type,'characters':len(text)},status=201)
    return Response([{'id':s.id,'title':s.title,'type':s.source_type,'topic':s.topic.name if s.topic else '', 'created_at':s.created_at.isoformat()} for s in request.user.sources.all().order_by('-created_at')])

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate(request):
    subject=request.data.get('subject','').strip(); topic_name=request.data.get('topic','').strip(); title=request.data.get('source_title','My notes').strip(); count=min(30,max(1,int(request.data.get('count',8))))
    upload=request.FILES.get('file'); text=request.data.get('notes','') or ''; source_type='notes'
    if upload:
        text,source_type=extract_file(upload); title=title or upload.name
    if not subject or not topic_name or not text.strip(): return Response({'error':'subject, topic and notes/file are required'},status=400)
    topic,_=Topic.objects.get_or_create(user=request.user,subject=subject,name=topic_name)
    src=Source.objects.create(user=request.user,topic=topic,title=title,file_name=upload.name if upload else '',source_type=source_type,text=text)
    cards,ai=generate_cards(subject,topic_name,title,text,count); out=[]
    lines=text.splitlines()
    for i,c in enumerate(cards):
        st=max(1,min(len(lines),c['line_start'])); en=max(st,min(len(lines),c['line_end'])); excerpt='\n'.join(lines[st-1:en])
        out.append({'id':f'generated-{i}','topic':topic_name,'q':c['prompt'],'a':c['answer'],'source':{'title':title,'lineStart':st,'lineEnd':en,'excerpt':excerpt},'type':'basic'})
    return Response({'cards':out,'count':len(out),'ai':ai,'source_id':src.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_cards(request):
    data=request.data.get('cards',[]); saved=[]
    for x in data:
        topic_name=x.get('topic','Unsorted'); subject=x.get('subject','General'); topic,_=Topic.objects.get_or_create(user=request.user,subject=subject,name=topic_name)
        src=None; source=x.get('source') or {}
        sid=source.get('id') or request.data.get('source_id')
        if sid: src=Source.objects.filter(id=sid,user=request.user).first()
        if not src and source.get('title'): src=Source.objects.filter(user=request.user,title=source.get('title')).order_by('-id').first()
        c=Card.objects.create(user=request.user,topic=topic,source=src,card_type=x.get('type','basic'),prompt=x.get('q',x.get('prompt','')),answer=x.get('a',x.get('answer','')),line_start=source.get('lineStart'),line_end=source.get('lineEnd'),excerpt=source.get('excerpt',''))
        saved.append(serialize_card(c))
    return Response({'saved':saved,'count':len(saved)},status=201)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def card_list(request):
    cards=request.user.cards.select_related('topic','source').order_by('-updated_at','-id')
    return Response([serialize_card(c) for c in cards])

@api_view(['PATCH','DELETE'])
@permission_classes([IsAuthenticated])
def card_detail(request,pk):
    card=Card.objects.filter(id=pk,user=request.user).select_related('topic','source').first()
    if not card:return Response({'error':'Card not found'},status=404)
    if request.method=='DELETE':
        card.delete()
        return Response({'ok':True})
    data=request.data
    prompt=data.get('q',data.get('prompt',card.prompt)).strip()
    answer=data.get('a',data.get('answer',card.answer)).strip()
    if not prompt or not answer:return Response({'error':'Front and back content are required'},status=400)
    card.prompt=prompt
    card.answer=answer
    if 'type' in data:
        card_type=data['type']
        if card_type not in dict(Card.TYPES):return Response({'error':'Invalid card type'},status=400)
        card.card_type=card_type
    if 'topic' in data or 'subject' in data:
        topic_name=str(data.get('topic','')).strip()
        subject=str(data.get('subject','')).strip()
        if topic_name:
            if not subject:subject='General'
            card.topic,_=Topic.objects.get_or_create(user=request.user,subject=subject,name=topic_name)
        else:
            card.topic=None
    card.save()
    return Response(serialize_card(card))

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def due_cards(request):
    now=timezone.now(); due=request.user.cards.filter(due_at__lte=now)
    qs=due.select_related('topic','source').order_by('due_at','reps','id')
    limit=Profile.objects.get_or_create(user=request.user)[0].daily_review_limit
    counts={state:0 for state,_ in Card.STATES}
    counts.update({row['state']:row['count'] for row in due.values('state').annotate(count=Count('id'))})
    return Response({'cards':[serialize_card(c) for c in qs[:limit]],'counts':counts})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review(request,pk):
    c=Card.objects.filter(id=pk,user=request.user).first()
    if not c:return Response({'error':'Card not found'},status=404)
    rating=request.data.get('rating','good'); old,new,due=schedule(c,rating)
    ReviewLog.objects.create(user=request.user,card=c,rating=rating,from_state=old,to_state=new,response_ms=int(request.data.get('response_ms',0)),scheduled_at=due)
    return Response({'card':serialize_card(c),'from_state':old,'to_state':new,'due_at':due.isoformat()})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    now=timezone.now(); cards=request.user.cards.all(); reviews=request.user.reviews.all()
    return Response({'stats':{'cards':cards.count(),'due':cards.filter(due_at__lte=now).count(),'reviews':reviews.count(),'topics':request.user.topics.count(),'sources':request.user.sources.count(),'mains':request.user.mains_submissions.count()},'states':{s:cards.filter(state=s).count() for s,_ in Card.STATES},'subjects':[{'name':x['topic__subject'],'cards':x['n']} for x in cards.values('topic__subject').annotate(n=Count('id')).order_by('-n')[:8]]})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mains(request):
    q=request.data.get('question','').strip(); a=request.data.get('answer','').strip(); m=int(request.data.get('max_marks',10)); upload=request.FILES.get('answer_file')
    if not q or (not a and not upload):return Response({'error':'question and an answer text, dictation transcript, image, or PDF are required'},status=400)
    ev=evaluate_mains(q,a,m,upload); sub=MainsSubmission.objects.create(user=request.user,question=q,answer=a,max_marks=m,marks=float(ev.get('marks',0)),evaluation=ev)
    for kw in ev.get('keywords',[]): MemoryItem.objects.create(user=request.user,item_type='keyword',text=kw,source_submission=sub)
    for ex in ev.get('examples',[]) if isinstance(ev.get('examples'),list) else []: MemoryItem.objects.create(user=request.user,item_type='example',text=str(ex),source_submission=sub)
    return Response({'id':sub.id,'marks':sub.marks,'max_marks':m,'evaluation':ev,'ai':not str(ev.get('summary','')).startswith('AI evaluation is not configured') and 'AI evaluation was unavailable' not in str(ev.get('summary',''))},status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mains_model_answer(request):
    question=request.data.get('question','').strip()
    try: max_marks=max(1,min(100,int(request.data.get('max_marks',10))))
    except (TypeError,ValueError): max_marks=10
    if not question: return Response({'error':'A Mains question is required.'},status=400)
    try:
        result=generate_model_answer(question,max_marks)
        return Response({**result,'max_marks':max_marks})
    except Exception as exc:
        return Response({'error':str(exc)},status=502)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mains_evaluations(request):
    qs=request.user.mains_submissions.all()
    query=request.query_params.get('q','').strip()
    if query:
        from django.db.models import Q
        qs=qs.filter(Q(question__icontains=query)|Q(answer__icontains=query))
    try: limit=max(1,min(100,int(request.query_params.get('limit',5))))
    except (TypeError,ValueError): limit=5
    qs=qs.order_by('-created_at')[:limit]
    return Response([{'id':s.id,'question':s.question,'answer':s.answer,'marks':s.marks,'max_marks':s.max_marks,'evaluation':s.evaluation,'created_at':s.created_at.isoformat()} for s in qs])


@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def pyqs(request):
    if request.method=='POST':
        t=Topic.objects.filter(id=request.data.get('topic_id'),user=request.user).first() if request.data.get('topic_id') else None
        q=PYQ.objects.create(user=request.user,year=int(request.data.get('year',2026)),exam=request.data.get('exam','UPSC CSE'),paper=request.data.get('paper','Prelims'),question=request.data.get('question',''),answer=request.data.get('answer',''),subject=request.data.get('subject','General'),topic=t)
        return Response({'id':q.id,'year':q.year,'question':q.question},status=201)
    return Response([{'id':q.id,'year':q.year,'exam':q.exam,'paper':q.paper,'question':q.question,'answer':q.answer,'subject':q.subject,'topic':q.topic.name if q.topic else ''} for q in request.user.pyqs.all().order_by('-year','-id')])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exam_mode(request):
    now=timezone.now(); cards=list(request.user.cards.filter(due_at__lte=now).order_by('due_at')[:10]); pyq=list(request.user.pyqs.order_by('?')[:5])
    return Response({'recall':[serialize_card(c) for c in cards],'pyqs':[{'id':q.id,'year':q.year,'question':q.question,'paper':q.paper,'subject':q.subject} for q in pyq]})

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def memory_items(request):
    if request.method=='POST':
        m=MemoryItem.objects.create(user=request.user,item_type=request.data.get('item_type','keyword'),text=request.data.get('text',''))
        return Response({'id':m.id,'item_type':m.item_type,'text':m.text},status=201)
    return Response([{'id':m.id,'item_type':m.item_type,'text':m.text,'created_at':m.created_at.isoformat()} for m in request.user.memory_items.all().order_by('-created_at')])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knowledge_graph(request):
    nodes=[]; edges=[]
    for t in request.user.topics.all():
        tid=f't{t.id}'; nodes.append({'id':tid,'type':'topic','label':f'{t.subject} · {t.name}'})
        for c in t.cards.all():
            cid=f'c{c.id}'; nodes.append({'id':cid,'type':'card','label':c.prompt[:70]}); edges.append({'from':tid,'to':cid})
        for q in t.pyq_set.all():
            qid=f'q{q.id}'; nodes.append({'id':qid,'type':'pyq','label':f'{q.year} · {q.question[:60]}'}); edges.append({'from':tid,'to':qid})
    return Response({'nodes':nodes,'edges':edges})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics(request):
    cards=request.user.cards.all(); logs=request.user.reviews.all(); now=timezone.now()
    return Response({'total_cards':cards.count(),'due':cards.filter(due_at__lte=now).count(),'again':logs.filter(rating='again').count(),'good':logs.filter(rating='good').count(),'hard':logs.filter(rating='hard').count(),'easy':logs.filter(rating='easy').count(),'avg_mains':request.user.mains_submissions.aggregate(x=Avg('marks'))['x'] or 0,'retrieval':{'reviewed':logs.count(),'successful':logs.filter(rating__in=['good','easy']).count()}})
