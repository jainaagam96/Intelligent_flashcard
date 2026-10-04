import json, re
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import Card

LEARNING_STEPS=[60,300,600]
RELEARNING_STEPS=[600,3600]

def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=settings.OPENAI_API_KEY,timeout=50.0,max_retries=0)

def extract_file(upload):
    name=(upload.name or '').lower()
    raw=upload.read()
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        import io
        reader=PdfReader(io.BytesIO(raw)); pages=[]
        for i,p in enumerate(reader.pages,1): pages.append(f'[Page {i}]\n{p.extract_text() or ""}')
        return '\n\n'.join(pages),'pdf'
    if name.endswith('.docx'):
        from docx import Document
        import io
        d=Document(io.BytesIO(raw)); return '\n'.join(p.text for p in d.paragraphs),'docx'
    return raw.decode('utf-8',errors='replace'),'notes'

def _fallback_cards(subject,topic,title,text,count):
    lines=text.splitlines(); cards=[]
    useful=[(i+1,l.strip()) for i,l in enumerate(lines) if l.strip()]
    for i,(n,l) in enumerate(useful[:count]):
        cards.append({'prompt':f'What is the key UPSC-relevant point stated in this note: “{l[:120]}”?', 'answer':l, 'line_start':n,'line_end':n})
    return cards

def generate_cards(subject,topic,title,text,count):
    if not settings.OPENAI_API_KEY:
        return _fallback_cards(subject,topic,title,text,count), False
    client=_openai_client()
    lines=text.splitlines(); numbered='\n'.join(f'{i+1}: {x}' for i,x in enumerate(lines))
    schema={'type':'object','additionalProperties':False,'properties':{'cards':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'prompt':{'type':'string'},'answer':{'type':'string'},'line_start':{'type':'integer','minimum':1},'line_end':{'type':'integer','minimum':1}},'required':['prompt','answer','line_start','line_end']}}},'required':['cards']}
    instructions='''You are the upscEasy UPSC Active Recall Generator. Use ONLY the supplied source notes. Do not add outside facts. Create atomic, testable retrieval prompts useful for UPSC Prelims/Mains. Cover definitions, provisions, causes/effects, comparisons, chronology, committees/cases, examples and multi-dimensional points only when supported. Avoid trivial prompts and duplicates. Every answer must be supported by the smallest useful contiguous source line range. Return only the requested JSON schema.'''
    try:
        r=client.responses.create(model=settings.OPENAI_MODEL,instructions=instructions,input=f'Subject: {subject}\nTopic: {topic}\nSource: {title}\nRequested cards: {count}\n\nSOURCE LINES:\n{numbered}',text={'format':{'type':'json_schema','name':'upsc_recall_cards','schema':schema,'strict':True}})
        data=json.loads(r.output_text); out=[]
        for c in data.get('cards',[])[:count]:
            s=max(1,min(len(lines),int(c['line_start']))); e=max(s,min(len(lines),int(c['line_end'])))
            out.append({'prompt':c['prompt'].strip(),'answer':c['answer'].strip(),'line_start':s,'line_end':e})
        return out, True
    except Exception:
        return _fallback_cards(subject,topic,title,text,count), False

def schedule(card,rating):
    now=timezone.now(); old=card.state; ease=card.ease; step=card.learning_step; interval=card.interval_days
    rating=rating.lower()
    if old=='new':
        card.state='learning'; card.learning_step=0
        if rating=='again': mins=1
        elif rating=='hard': mins=5
        elif rating=='good': card.learning_step=1; mins=10
        else: card.state='review'; card.interval_days=4; card.learning_step=0; mins=4*1440
    elif old=='learning':
        if rating=='again': card.learning_step=0; mins=1
        elif rating=='hard': mins=5
        elif rating=='good':
            if card.learning_step < len(LEARNING_STEPS)-1: card.learning_step+=1; mins=LEARNING_STEPS[card.learning_step]/60
            else: card.state='review'; card.interval_days=1; card.learning_step=0; mins=1440
        else: card.state='review'; card.interval_days=4; card.learning_step=0; mins=4*1440
    elif old=='review':
        if rating=='again': card.state='relearning'; card.learning_step=0; card.lapses+=1; mins=10
        else:
            mult={'hard':1.2,'good':card.ease,'easy':card.ease+1.3}[rating]
            if rating=='hard': card.ease=max(1.3,card.ease-.1)
            if rating=='easy': card.ease=min(3.5,card.ease+.15)
            card.interval_days=max(1,interval*mult if interval else {'hard':1,'good':1,'easy':4}[rating])
            mins=card.interval_days*1440
    else:
        if rating=='again': card.learning_step=0; mins=10
        elif rating=='hard': card.learning_step=1; mins=60
        elif rating=='good': card.state='review'; mins=max(1440,card.interval_days*1440)
        else: card.state='review'; card.interval_days=max(2,card.interval_days*1.5); mins=card.interval_days*1440
    card.due_at=now+timedelta(minutes=mins); card.reps+=1; card.last_reviewed=now; card.last_rating=rating; card.save()
    return old,card.state,card.due_at

def evaluate_mains(question, answer, max_marks, answer_upload=None):
    """Evaluate a UPSC Mains answer from typed/dictated text or a scanned image/PDF."""
    max_marks = max(1, int(max_marks or 10))
    answer = (answer or '').strip()
    words = len(answer.split())

    def fallback(reason='AI evaluation is not configured; showing local evaluation.'):
        length_factor = min(1.0, words / 180.0)
        structure = min(100, round(35 + length_factor * 55)) if words else 0
        content = min(100, round(25 + length_factor * 60)) if words else 0
        examples = 0
        score_ratio = min(0.75, 0.20 + length_factor * 0.45) if words else 0
        marks = round(max_marks * score_ratio, 1)
        return {
            'marks': marks, 'summary': reason, 'content': content, 'structure': structure,
            'examples': examples, 'keywords': [],
            'omissions': [
                'Add specific constitutional provisions, committees, cases, data or examples where relevant.',
                'Use a clear introduction, structured body with multiple dimensions, and a concise conclusion.'
            ],
            'dimensions': ['Introduction', 'Core arguments', 'Multiple dimensions', 'Examples/evidence', 'Conclusion']
        }

    if not settings.OPENAI_API_KEY:
        return fallback()

    try:
        import base64, mimetypes
        client = _openai_client()
        schema = {
            'type':'object', 'additionalProperties':False,
            'properties':{
                'marks':{'type':'number'}, 'summary':{'type':'string'},
                'content':{'type':'number'}, 'structure':{'type':'number'},
                'examples':{'type':'array','items':{'type':'string'}},
                'keywords':{'type':'array','items':{'type':'string'}},
                'omissions':{'type':'array','items':{'type':'string'}},
                'dimensions':{'type':'array','items':{'type':'string'}},
                'rubric':{'type':'array','items':{
                    'type':'object','additionalProperties':False,
                    'properties':{'criterion':{'type':'string','enum':['Context and Directive','Content, Evidence and Analysis','Language and Expression','Introduction','Structure, Presentation and Visuals','Conclusion']},'score':{'type':'integer','minimum':1,'maximum':5},'feedback':{'type':'string'}},
                    'required':['criterion','score','feedback']
                }}
            },
            'required':['marks','summary','content','structure','examples','keywords','omissions','dimensions','rubric']
        }
        instructions = (
            'Evaluate a UPSC Civil Services Mains answer neutrally and constructively. '
            'The answer may be typed, dictated, handwritten in a scanned image, or contained in a scanned PDF. '
            'If an image/PDF is supplied, carefully read the handwriting and evaluate only what is actually legible. '
            'Do not invent words, facts, examples or arguments that are not present. Mention uncertainty in the summary if handwriting is unclear. '
            'UPSC does not publish a fixed question-level marking formula. Imitate a careful examiner-style practice assessment, not an official UPSC score. '
            'Assess the answer holistically against the question demand; do not apply fixed percentages or calculate marks by averaging the trait scores. The overall mark is a question-specific judgment informed by these traits. '
            'Return one entry for each of these six indicators: Context and Directive; Content, Evidence and Analysis; Language and Expression; Introduction; Structure, Presentation and Visuals; Conclusion. '
            'Score each indicator on this anchored 1–5 scale: 1 Poor, 2 Average, 3 Good, 4 Excellent, 5 Outstanding. Give specific evidence from the answer and one practical improvement for each. '
            'Context and Directive: identify the key demand/command word and whether every part is answered in the right mode. '
            'Content, Evidence and Analysis: relevance, accuracy, depth, supported arguments, examples/facts/data, and suitable dimensions; reward original interpretation only when reasoned and supported. '
            'Language and Expression: clear, concise sentences and appropriate technical terms; assess language from text, not handwriting. '
            'Introduction: relevant opening that frames the issue, context or definition without wasting space. '
            'Structure, Presentation and Visuals: logical order reflecting the question parts, readable paragraphs/headings/bullets, and useful diagrams/maps/flowcharts where suitable. Assess legibility/neatness only from an uploaded scan; do not penalize typed answers for not showing handwriting or visuals that the question does not call for. '
            'Conclusion: concise synthesis, balanced judgment or relevant way forward that answers the question. '
            'Keep feedback concrete: cite what is present, what is missing, and how to improve it. Mention uncertainty when handwriting is unclear. '
            'Marks must be within 0 and the supplied maximum. Return only the requested JSON schema.'
        )
        content_parts=[{'type':'input_text','text':f'Max marks: {max_marks}\nQUESTION:\n{question}\n\nTYPED/DICATED ANSWER TEXT:\n{answer or "(No typed text; inspect the attached answer.)"}'}]
        if answer_upload:
            raw=answer_upload.read()
            name=(answer_upload.name or 'answer').lower()
            mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if not raw:
                raise ValueError('The uploaded answer file is empty.')
            if len(raw) > 15 * 1024 * 1024:
                raise ValueError('The answer upload is larger than 15 MB. Please upload a smaller scan/PDF.')
            if mime.startswith('image/'):
                data=base64.b64encode(raw).decode('ascii')
                content_parts.append({'type':'input_image','image_url':f'data:{mime};base64,{data}'})
            elif mime=='application/pdf' or name.endswith('.pdf'):
                uploaded=client.files.create(file=(answer_upload.name or 'answer.pdf', raw, 'application/pdf'), purpose='user_data')
                content_parts.append({'type':'input_file','file_id':uploaded.id})
            else:
                raise ValueError('Unsupported answer file. Upload an image or PDF.')
        r = client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=instructions,
            input=[{'role':'user','content':content_parts}],
            text={'format':{'type':'json_schema','name':'mains_evaluation','schema':schema,'strict':True}}
        )
        ev=json.loads(r.output_text)
        for key in ('keywords','examples','omissions','dimensions'):
            if not isinstance(ev.get(key),list): ev[key]=[]
        rubric=ev.get('rubric') if isinstance(ev.get('rubric'),list) else []
        rubric_by_name={item.get('criterion'):item for item in rubric if isinstance(item,dict)}
        criteria=['Context and Directive','Content, Evidence and Analysis','Language and Expression','Introduction','Structure, Presentation and Visuals','Conclusion']
        if all(name in rubric_by_name for name in criteria):
            for name,item in rubric_by_name.items():
                item['score']=max(1,min(5,int(item.get('score',1))))
            ev['rubric']=[rubric_by_name[name] for name in criteria]
            ev['content']=rubric_by_name['Content, Evidence and Analysis']['score']
            ev['structure']=rubric_by_name['Structure, Presentation and Visuals']['score']
        else:
            ev['marks']=round(min(float(max_marks),max(0.0,float(ev.get('marks',0)))),1)
            ev['rubric']=[]
        return ev
    except Exception as exc:
        # Surface the API's non-secret diagnostic message so local users can
        # distinguish rate limits, exhausted credits, and other request errors.
        detail = getattr(exc, 'message', None) or str(exc)
        code = getattr(exc, 'code', None)
        diagnostic = f' ({code})' if code else ''
        return fallback(f'AI evaluation was unavailable ({type(exc).__name__}{diagnostic}): {detail}. A local evaluation is shown instead.')

def generate_model_answer(question, max_marks):
    client=_openai_client()
    schema={
        'type':'object','additionalProperties':False,
        'properties':{'answer':{'type':'string'},'demand_summary':{'type':'string'}},
        'required':['answer','demand_summary']
    }
    instructions=(
        'Write a strong, realistic UPSC Civil Services Mains General Studies model answer to the supplied question. '
        'First interpret every part of the question and its directive (for example discuss, analyse, critically examine, evaluate). '
        'Use a concise introduction, a logically organized body with short headings or bullets where useful, and a balanced conclusion that directly answers the demand. '
        'Use relevant facts, constitutional/legal references, examples and multiple dimensions only when confidently accurate and relevant. '
        'Do not invent statistics, citations, committees, cases, schemes, quotations or current facts. If uncertain, use a general accurate formulation instead. '
        'Keep length proportionate to the supplied marks and follow any word limit in the question. Do not claim this is an official UPSC answer or official marking key. '
        'Return the answer in plain text with clear line breaks; return a short demand_summary explaining the directive and key parts addressed.'
    )
    try:
        r=client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=instructions,
            input=f'Marks: {max_marks}\nQuestion:\n{question}',
            text={'format':{'type':'json_schema','name':'upsc_mains_model_answer','schema':schema,'strict':True}}
        )
        data=json.loads(r.output_text)
        answer=data.get('answer','').strip()
        if not answer: raise ValueError('The model returned an empty answer.')
        return {'answer':answer,'demand_summary':data.get('demand_summary','').strip(),'word_count':len(answer.split())}
    except Exception as exc:
        detail=getattr(exc,'message',None) or str(exc)
        code=getattr(exc,'code',None)
        suffix=f' ({code})' if code else ''
        raise RuntimeError(f'Model answer generation failed: {type(exc).__name__}{suffix}: {detail}') from exc
