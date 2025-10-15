"""
Lightweight lemmatization for RU/EN action verbs without heavy dependencies.

Approach:
- EN: Simple stemming + conjugation table for common action verbs
- RU: Mini-dictionary of lemmas for top-100 action verbs + imperative rules
- Configurable: custom verb extensions via config

No heavy dependencies (spaCy, pymorphy2) - pure rule-based + lookup tables.
"""
import re
from typing import Dict, List, Set
import structlog

logger = structlog.get_logger()


class LightweightLemmatizer:
    """Lightweight lemmatization for RU/EN action verbs."""
    
    def __init__(self, custom_verbs: Dict[str, str] = None):
        """
        Initialize lemmatizer.
        
        Args:
            custom_verbs: Dict mapping verb form → lemma for custom extensions
        """
        self.custom_verbs = custom_verbs or {}
        
        # EN: Common action verbs conjugation table
        self.en_verb_table = self._build_en_verb_table()
        
        # RU: Top-100 action verbs lemma table
        self.ru_verb_table = self._build_ru_verb_table()
        
        # Merge custom verbs
        self.en_verb_table.update(self.custom_verbs)
        self.ru_verb_table.update(self.custom_verbs)
    
    def _build_en_verb_table(self) -> Dict[str, str]:
        """
        Build English verb conjugation table.
        
        Common action verbs: ask, provide, check, update, confirm, send, review, approve, etc.
        """
        verbs = {
            # Base forms
            'ask': 'ask', 'provide': 'provide', 'check': 'check', 'update': 'update',
            'confirm': 'confirm', 'send': 'send', 'review': 'review', 'approve': 'approve',
            'complete': 'complete', 'finish': 'finish', 'deliver': 'deliver', 'submit': 'submit',
            'prepare': 'prepare', 'create': 'create', 'schedule': 'schedule', 'arrange': 'arrange',
            'coordinate': 'coordinate', 'organize': 'organize', 'verify': 'verify', 'validate': 'validate',
            'investigate': 'investigate', 'resolve': 'resolve', 'fix': 'fix', 'implement': 'implement',
            'discuss': 'discuss', 'meet': 'meet', 'call': 'call', 'contact': 'contact',
            'inform': 'inform', 'notify': 'notify', 'remind': 'remind', 'follow': 'follow',
            'escalate': 'escalate', 'prioritize': 'prioritize', 'decide': 'decide', 'determine': 'determine',
            
            # Past tense (-ed)
            'asked': 'ask', 'provided': 'provide', 'checked': 'check', 'updated': 'update',
            'confirmed': 'confirm', 'sent': 'send', 'reviewed': 'review', 'approved': 'approve',
            'completed': 'complete', 'finished': 'finish', 'delivered': 'deliver', 'submitted': 'submit',
            'prepared': 'prepare', 'created': 'create', 'scheduled': 'schedule', 'arranged': 'arrange',
            'coordinated': 'coordinate', 'organized': 'organize', 'verified': 'verify', 'validated': 'validate',
            'investigated': 'investigate', 'resolved': 'resolve', 'fixed': 'fix', 'implemented': 'implement',
            'discussed': 'discuss', 'met': 'meet', 'called': 'call', 'contacted': 'contact',
            'informed': 'inform', 'notified': 'notify', 'reminded': 'remind', 'followed': 'follow',
            'escalated': 'escalate', 'prioritized': 'prioritize', 'decided': 'decide', 'determined': 'determine',
            
            # Present continuous (-ing)
            'asking': 'ask', 'providing': 'provide', 'checking': 'check', 'updating': 'update',
            'confirming': 'confirm', 'sending': 'send', 'reviewing': 'review', 'approving': 'approve',
            'completing': 'complete', 'finishing': 'finish', 'delivering': 'deliver', 'submitting': 'submit',
            'preparing': 'prepare', 'creating': 'create', 'scheduling': 'schedule', 'arranging': 'arrange',
            'coordinating': 'coordinate', 'organizing': 'organize', 'verifying': 'verify', 'validating': 'validate',
            'investigating': 'investigate', 'resolving': 'resolve', 'fixing': 'fix', 'implementing': 'implement',
            'discussing': 'discuss', 'meeting': 'meet', 'calling': 'call', 'contacting': 'contact',
            'informing': 'inform', 'notifying': 'notify', 'reminding': 'remind', 'following': 'follow',
            'escalating': 'escalate', 'prioritizing': 'prioritize', 'deciding': 'decide', 'determining': 'determine',
            
            # Third person singular (-s)
            'asks': 'ask', 'provides': 'provide', 'checks': 'check', 'updates': 'update',
            'confirms': 'confirm', 'sends': 'send', 'reviews': 'review', 'approves': 'approve',
            'completes': 'complete', 'finishes': 'finish', 'delivers': 'deliver', 'submits': 'submit',
            'prepares': 'prepare', 'creates': 'create', 'schedules': 'schedule', 'arranges': 'arrange',
            'coordinates': 'coordinate', 'organizes': 'organize', 'verifies': 'verify', 'validates': 'validate',
            'investigates': 'investigate', 'resolves': 'resolve', 'fixes': 'fix', 'implements': 'implement',
            'discusses': 'discuss', 'meets': 'meet', 'calls': 'call', 'contacts': 'contact',
            'informs': 'inform', 'notifies': 'notify', 'reminds': 'remind', 'follows': 'follow',
            'escalates': 'escalate', 'prioritizes': 'prioritize', 'decides': 'decide', 'determines': 'determine',
        }
        
        return verbs
    
    def _build_ru_verb_table(self) -> Dict[str, str]:
        """
        Build Russian verb lemma table.
        
        Top-100 action verbs with common forms (infinitive, imperative, conjugations).
        """
        verbs = {
            # сделать (to do/make)
            'сделать': 'сделать', 'сделай': 'сделать', 'сделайте': 'сделать',
            'сделаю': 'сделать', 'сделаешь': 'сделать', 'сделает': 'сделать',
            'сделаем': 'сделать', 'сделаете': 'сделать', 'сделают': 'сделать',
            'сделал': 'сделать', 'сделала': 'сделать', 'сделали': 'сделать',
            
            # проверить (to check)
            'проверить': 'проверить', 'проверь': 'проверить', 'проверьте': 'проверить',
            'проверю': 'проверить', 'проверишь': 'проверить', 'проверит': 'проверить',
            'проверим': 'проверить', 'проверите': 'проверить', 'проверят': 'проверить',
            'проверил': 'проверить', 'проверила': 'проверить', 'проверили': 'проверить',
            
            # прислать (to send)
            'прислать': 'прислать', 'пришли': 'прислать', 'пришлите': 'прислать',
            'пришлю': 'прислать', 'пришлёшь': 'прислать', 'пришлёт': 'прислать',
            'пришлем': 'прислать', 'пришлете': 'прислать', 'пришлют': 'прислать',
            'прислал': 'прислать', 'прислала': 'прислать', 'прислали': 'прислать',
            
            # подтвердить (to confirm)
            'подтвердить': 'подтвердить', 'подтверди': 'подтвердить', 'подтвердите': 'подтвердить',
            'подтвержу': 'подтвердить', 'подтвердишь': 'подтвердить', 'подтвердит': 'подтвердить',
            'подтвердим': 'подтвердить', 'подтвердите': 'подтвердить', 'подтвердят': 'подтвердить',
            'подтвердил': 'подтвердить', 'подтвердила': 'подтвердить', 'подтвердили': 'подтвердить',
            
            # уточнить (to clarify)
            'уточнить': 'уточнить', 'уточни': 'уточнить', 'уточните': 'уточнить',
            'уточню': 'уточнить', 'уточнишь': 'уточнить', 'уточнит': 'уточнить',
            'уточним': 'уточнить', 'уточните': 'уточнить', 'уточнят': 'уточнить',
            'уточнил': 'уточнить', 'уточнила': 'уточнить', 'уточнили': 'уточнить',
            
            # договориться (to agree/arrange)
            'договориться': 'договориться', 'договорись': 'договориться', 'договоритесь': 'договориться',
            'договорюсь': 'договориться', 'договоришься': 'договориться', 'договорится': 'договориться',
            'договоримся': 'договориться', 'договоритесь': 'договориться', 'договорятся': 'договориться',
            'договорился': 'договориться', 'договорилась': 'договориться', 'договорились': 'договориться',
            
            # перенести (to reschedule/move)
            'перенести': 'перенести', 'перенеси': 'перенести', 'перенесите': 'перенести',
            'перенесу': 'перенести', 'перенесёшь': 'перенести', 'перенесёт': 'перенести',
            'перенесем': 'перенести', 'перенесете': 'перенести', 'перенесут': 'перенести',
            'перенес': 'перенести', 'перенесла': 'перенести', 'перенесли': 'перенести',
            
            # собрать (to collect/gather)
            'собрать': 'собрать', 'собери': 'собрать', 'соберите': 'собрать',
            'соберу': 'собрать', 'соберёшь': 'собрать', 'соберёт': 'собрать',
            'соберем': 'собрать', 'соберете': 'собрать', 'соберут': 'собрать',
            'собрал': 'собрать', 'собрала': 'собрать', 'собрали': 'собрать',
            
            # подготовить (to prepare)
            'подготовить': 'подготовить', 'подготовь': 'подготовить', 'подготовьте': 'подготовить',
            'подготовлю': 'подготовить', 'подготовишь': 'подготовить', 'подготовит': 'подготовить',
            'подготовим': 'подготовить', 'подготовите': 'подготовить', 'подготовят': 'подготовить',
            'подготовил': 'подготовить', 'подготовила': 'подготовить', 'подготовили': 'подготовить',
            
            # отправить (to send)
            'отправить': 'отправить', 'отправь': 'отправить', 'отправьте': 'отправить',
            'отправлю': 'отправить', 'отправишь': 'отправить', 'отправит': 'отправить',
            'отправим': 'отправить', 'отправите': 'отправить', 'отправят': 'отправить',
            'отправил': 'отправить', 'отправила': 'отправить', 'отправили': 'отправить',
            
            # согласовать (to approve/coordinate)
            'согласовать': 'согласовать', 'согласуй': 'согласовать', 'согласуйте': 'согласовать',
            'согласую': 'согласовать', 'согласуешь': 'согласовать', 'согласует': 'согласовать',
            'согласуем': 'согласовать', 'согласуете': 'согласовать', 'согласуют': 'согласовать',
            'согласовал': 'согласовать', 'согласовала': 'согласовать', 'согласовали': 'согласовать',
            
            # обсудить (to discuss)
            'обсудить': 'обсудить', 'обсуди': 'обсудить', 'обсудите': 'обсудить',
            'обсужу': 'обсудить', 'обсудишь': 'обсудить', 'обсудит': 'обсудить',
            'обсудим': 'обсудить', 'обсудите': 'обсудить', 'обсудят': 'обсудить',
            'обсудил': 'обсудить', 'обсудила': 'обсудить', 'обсудили': 'обсудить',
            
            # решить (to decide/solve)
            'решить': 'решить', 'реши': 'решить', 'решите': 'решить',
            'решу': 'решить', 'решишь': 'решить', 'решит': 'решить',
            'решим': 'решить', 'решите': 'решить', 'решат': 'решить',
            'решил': 'решить', 'решила': 'решить', 'решили': 'решить',
            
            # организовать (to organize)
            'организовать': 'организовать', 'организуй': 'организовать', 'организуйте': 'организовать',
            'организую': 'организовать', 'организуешь': 'организовать', 'организует': 'организовать',
            'организуем': 'организовать', 'организуете': 'организовать', 'организуют': 'организовать',
            'организовал': 'организовать', 'организовала': 'организовать', 'организовали': 'организовать',
            
            # ответить (to reply/answer)
            'ответить': 'ответить', 'ответь': 'ответить', 'ответьте': 'ответить',
            'отвечу': 'ответить', 'ответишь': 'ответить', 'ответит': 'ответить',
            'ответим': 'ответить', 'ответите': 'ответить', 'ответят': 'ответить',
            'ответил': 'ответить', 'ответила': 'ответить', 'ответили': 'ответить',
            
            # предоставить (to provide)
            'предоставить': 'предоставить', 'предоставь': 'предоставить', 'предоставьте': 'предоставить',
            'предоставлю': 'предоставить', 'предоставишь': 'предоставить', 'предоставит': 'предоставить',
            'предоставим': 'предоставить', 'предоставите': 'предоставить', 'предоставят': 'предоставить',
            'предоставил': 'предоставить', 'предоставила': 'предоставить', 'предоставили': 'предоставить',
            
            # дать (to give)
            'дать': 'дать', 'дай': 'дать', 'дайте': 'дать',
            'дам': 'дать', 'дашь': 'дать', 'даст': 'дать',
            'дадим': 'дать', 'дадите': 'дать', 'дадут': 'дать',
            'дал': 'дать', 'дала': 'дать', 'дали': 'дать',
            
            # взять (to take)
            'взять': 'взять', 'возьми': 'взять', 'возьмите': 'взять',
            'возьму': 'взять', 'возьмёшь': 'взять', 'возьмёт': 'взять',
            'возьмем': 'взять', 'возьмете': 'взять', 'возьмут': 'взять',
            'взял': 'взять', 'взяла': 'взять', 'взяли': 'взять',
            
            # написать (to write)
            'написать': 'написать', 'напиши': 'написать', 'напишите': 'написать',
            'напишу': 'написать', 'напишешь': 'написать', 'напишет': 'написать',
            'напишем': 'написать', 'напишете': 'написать', 'напишут': 'написать',
            'написал': 'написать', 'написала': 'написать', 'написали': 'написать',
            
            # позвонить (to call)
            'позвонить': 'позвонить', 'позвони': 'позвонить', 'позвоните': 'позвонить',
            'позвоню': 'позвонить', 'позвонишь': 'позвонить', 'позвонит': 'позвонить',
            'позвоним': 'позвонить', 'позвоните': 'позвонить', 'позвонят': 'позвонить',
            'позвонил': 'позвонить', 'позвонила': 'позвонить', 'позвонили': 'позвонить',
            
            # встретиться (to meet)
            'встретиться': 'встретиться', 'встреться': 'встретиться', 'встретьтесь': 'встретиться',
            'встречусь': 'встретиться', 'встретишься': 'встретиться', 'встретится': 'встретиться',
            'встретимся': 'встретиться', 'встретитесь': 'встретиться', 'встретятся': 'встретиться',
            'встретился': 'встретиться', 'встретилась': 'встретиться', 'встретились': 'встретиться',
        }
        
        return verbs
    
    def lemmatize_token(self, token: str, lang: str = 'auto') -> str:
        """
        Lemmatize single token.
        
        Args:
            token: Word token to lemmatize
            lang: Language ('en', 'ru', 'auto')
        
        Returns:
            Lemmatized token (or original if not found)
        """
        token_lower = token.lower().strip()
        
        if not token_lower:
            return token
        
        # Auto-detect language if needed
        if lang == 'auto':
            # Simple heuristic: Cyrillic = Russian
            if re.search(r'[а-яА-ЯёЁ]', token):
                lang = 'ru'
            else:
                lang = 'en'
        
        # Lookup in appropriate table
        if lang == 'ru':
            lemma = self.ru_verb_table.get(token_lower)
            if lemma:
                return lemma
            
            # Apply imperative rules
            lemma = self._ru_imperative_rules(token_lower)
            if lemma:
                return lemma
        
        elif lang == 'en':
            lemma = self.en_verb_table.get(token_lower)
            if lemma:
                return lemma
            
            # Apply simple stemming for -ed/-ing endings
            lemma = self._en_simple_stem(token_lower)
            if lemma:
                return lemma
        
        # Return original if no lemma found
        return token_lower
    
    def _ru_imperative_rules(self, token: str) -> str:
        """
        Apply Russian imperative rules.
        
        Common patterns:
        - -йте → base (сделайте → сделать)
        - -ите → base + ить (проверите → проверить)
        """
        # Rule 1: -йте ending (imperative plural)
        if token.endswith('йте'):
            # сделайте → сделать
            base = token[:-3]
            candidates = [base + 'ать', base + 'ить', base + 'еть']
            for candidate in candidates:
                if candidate in self.ru_verb_table.values():
                    return candidate
        
        # Rule 2: -ите ending
        if token.endswith('ите') and len(token) > 4:
            # проверите → проверить
            base = token[:-3]
            candidate = base + 'ить'
            if candidate in self.ru_verb_table.values():
                return candidate
        
        # Rule 3: -и ending (imperative singular)
        if token.endswith('и') and len(token) > 2:
            base = token[:-1]
            candidates = [base + 'ить', base + 'еть', base + 'ать']
            for candidate in candidates:
                if candidate in self.ru_verb_table.values():
                    return candidate
        
        return None
    
    def _en_simple_stem(self, token: str) -> str:
        """
        Apply simple English stemming for common patterns.
        
        Patterns:
        - -ing → base (checking → check)
        - -ed → base (checked → check)
        - -s → base (checks → check)
        """
        # Rule 1: -ing
        if token.endswith('ing') and len(token) > 5:
            # checking → check
            base = token[:-3]
            # Handle doubling: running → run
            if len(base) >= 2 and base[-1] == base[-2]:
                base = base[:-1]
            if base in self.en_verb_table.values():
                return base
        
        # Rule 2: -ed
        if token.endswith('ed') and len(token) > 4:
            # checked → check
            base = token[:-2]
            if base in self.en_verb_table.values():
                return base
            # Handle -ied → -y: studied → study
            if token.endswith('ied'):
                base = token[:-3] + 'y'
                if base in self.en_verb_table.values():
                    return base
        
        # Rule 3: -s
        if token.endswith('s') and len(token) > 3:
            # checks → check
            base = token[:-1]
            if base in self.en_verb_table.values():
                return base
            # Handle -es: fixes → fix
            if token.endswith('es'):
                base = token[:-2]
                if base in self.en_verb_table.values():
                    return base
        
        return None
    
    def lemmatize_phrase(self, phrase: str, lang: str = 'auto') -> List[str]:
        """
        Lemmatize all tokens in phrase.
        
        Args:
            phrase: Text phrase
            lang: Language hint
        
        Returns:
            List of lemmatized tokens
        """
        # Simple tokenization (split on whitespace)
        tokens = phrase.split()
        
        lemmas = []
        for token in tokens:
            # Remove punctuation
            clean_token = re.sub(r'[^\w\s-]', '', token)
            if clean_token:
                lemma = self.lemmatize_token(clean_token, lang)
                lemmas.append(lemma)
        
        return lemmas
    
    def get_all_forms(self, lemma: str) -> Set[str]:
        """
        Get all known forms for a given lemma.
        
        Args:
            lemma: Base form of verb
        
        Returns:
            Set of all forms (conjugations) for this lemma
        """
        forms = set()
        
        # Search in EN table
        for form, base in self.en_verb_table.items():
            if base == lemma:
                forms.add(form)
        
        # Search in RU table
        for form, base in self.ru_verb_table.items():
            if base == lemma:
                forms.add(form)
        
        return forms

