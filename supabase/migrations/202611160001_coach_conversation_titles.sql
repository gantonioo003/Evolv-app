begin;

create function public.coach_opening_title(message text)
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  title_text text;
begin
  title_text := regexp_replace(message, 'https?://[^[:space:]<>]+|[[:alnum:]_.+%-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}', ' ', 'gi');
  title_text := regexp_replace(title_text, '(\+55[[:space:]]*)?\(?[1-9][0-9]\)?[ .-]?9?[0-9]{4}[ .-]?[0-9]{4}|[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}', ' ', 'g');
  title_text := regexp_replace(title_text, '\[(EMAIL|CPF|LINK|TELEFONE)\]', ' ', 'gi');
  title_text := btrim(regexp_replace(title_text, '[[:space:][:cntrl:]]+', ' ', 'g'), ' ,.!?;:–—…');
  title_text := regexp_replace(title_text,
    '^((oi+|ol[áa]+|opa|e a[ií]|bom dia|boa tarde|boa noite|tudo bem|tudo certo|beleza|blz|valeu|obrigad[oa])([ ,.!?;:–—…]+|$))+', '', 'i');
  title_text := regexp_replace(title_text,
    '^(por favor[ ,]+|qual( [ée])? |me (mostra|mostre|diz|diga|passa|passe|manda|mande|fala|fale) |pode (me )?)', '', 'i');
  title_text := regexp_replace(title_text, '^(o meu |a minha |meu |minha |o |a )', '', 'i');
  title_text := btrim(title_text, ' ,.!?;:–—…');
  if title_text !~ '[[:alpha:]]' then
    return null;
  end if;
  if char_length(title_text) > 60 then
    title_text := rtrim(coalesce(substring(title_text from '^.{1,59}[[:space:]]'), left(title_text, 59))) || '…';
  end if;
  return upper(left(title_text, 1)) || substring(title_text from 2);
end;
$$;

-- Keep the original activity dates while replacing legacy placeholder titles.
alter table public.coach_conversations disable trigger coach_conversations_set_updated_at;
with opening_titles as (
  select c.id, (
    select public.coach_opening_title(m.content)
    from public.coach_messages m
    where m.conversation_id = c.id and m.user_id = c.user_id and m.role = 'user'
      and public.coach_opening_title(m.content) is not null
    order by m.created_at, m.id
    limit 1
  ) as title
  from public.coach_conversations c
  where c.title is null or c.title = 'Nova conversa'
)
update public.coach_conversations c
set title = o.title
from opening_titles o
where c.id = o.id and c.title is distinct from o.title;
alter table public.coach_conversations enable trigger coach_conversations_set_updated_at;

create function public.set_coach_opening_title()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  update public.coach_conversations
  set title = public.coach_opening_title(new.content)
  where id = new.conversation_id and user_id = new.user_id and title is null
    and public.coach_opening_title(new.content) is not null;
  return new;
end;
$$;

create trigger coach_title_from_first_topic
after insert on public.coach_messages
for each row
when (new.role = 'user')
execute function public.set_coach_opening_title();

commit;
