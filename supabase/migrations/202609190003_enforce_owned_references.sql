-- Evolv - Ownership integrity for related user data
-- Prevents records owned by one user from referencing private records
-- owned by another user, including writes made outside the Data API.

create or replace function public.enforce_owned_reference()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  owner_user_id uuid;
  referenced_user_id uuid;
begin
  if tg_table_name in ('workout_plans', 'diet_plans') and new.goal_id is not null then
    select g.user_id
    into referenced_user_id
    from public.goals g
    where g.id = new.goal_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected goal belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'workout_logs' and new.workout_day_id is not null then
    select wp.user_id
    into referenced_user_id
    from public.workout_days wd
    join public.workout_plans wp on wp.id = wd.workout_plan_id
    where wd.id = new.workout_day_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected workout day belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'exercise_logs' and new.workout_log_id is not null then
    select wl.user_id
    into referenced_user_id
    from public.workout_logs wl
    where wl.id = new.workout_log_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected workout log belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'coach_messages' then
    select cc.user_id
    into referenced_user_id
    from public.coach_conversations cc
    where cc.id = new.conversation_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected Coach conversation belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'coach_memory_items' and new.source_message_id is not null then
    select cm.user_id
    into referenced_user_id
    from public.coach_messages cm
    where cm.id = new.source_message_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected Coach message belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'planner_adjustments' and new.conversation_id is not null then
    select cc.user_id
    into referenced_user_id
    from public.coach_conversations cc
    where cc.id = new.conversation_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected Coach conversation belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'progress_photos' and new.progress_entry_id is not null then
    select pe.user_id
    into referenced_user_id
    from public.progress_entries pe
    where pe.id = new.progress_entry_id;

    if found and referenced_user_id is distinct from new.user_id then
      raise exception 'The selected progress entry belongs to another user.'
        using errcode = '23514';
    end if;

  elsif tg_table_name = 'food_log_items' then
    select fl.user_id
    into owner_user_id
    from public.food_logs fl
    where fl.id = new.food_log_id;

    if found and owner_user_id is distinct from new.user_id then
      raise exception 'The selected food log belongs to another user.'
        using errcode = '23514';
    end if;

    if new.food_id is not null then
      select f.user_id
      into referenced_user_id
      from public.foods f
      where f.id = new.food_id;

      if found and referenced_user_id is not null and referenced_user_id is distinct from new.user_id then
        raise exception 'The selected custom food belongs to another user.'
          using errcode = '23514';
      end if;
    end if;

  elsif tg_table_name = 'meal_items' and new.food_id is not null then
    select dp.user_id
    into owner_user_id
    from public.meals m
    join public.diet_plans dp on dp.id = m.diet_plan_id
    where m.id = new.meal_id;

    select f.user_id
    into referenced_user_id
    from public.foods f
    where f.id = new.food_id;

    if found and referenced_user_id is not null and referenced_user_id is distinct from owner_user_id then
      raise exception 'The selected custom food belongs to another user.'
        using errcode = '23514';
    end if;
  end if;

  return new;
end;
$$;

create trigger workout_plans_enforce_owned_reference
before insert or update on public.workout_plans
for each row execute function public.enforce_owned_reference();

create trigger diet_plans_enforce_owned_reference
before insert or update on public.diet_plans
for each row execute function public.enforce_owned_reference();

create trigger workout_logs_enforce_owned_reference
before insert or update on public.workout_logs
for each row execute function public.enforce_owned_reference();

create trigger exercise_logs_enforce_owned_reference
before insert or update on public.exercise_logs
for each row execute function public.enforce_owned_reference();

create trigger coach_messages_enforce_owned_reference
before insert or update on public.coach_messages
for each row execute function public.enforce_owned_reference();

create trigger coach_memory_enforce_owned_reference
before insert or update on public.coach_memory_items
for each row execute function public.enforce_owned_reference();

create trigger planner_adjustments_enforce_owned_reference
before insert or update on public.planner_adjustments
for each row execute function public.enforce_owned_reference();

create trigger progress_photos_enforce_owned_reference
before insert or update on public.progress_photos
for each row execute function public.enforce_owned_reference();

create trigger food_log_items_enforce_owned_reference
before insert or update on public.food_log_items
for each row execute function public.enforce_owned_reference();

create trigger meal_items_enforce_owned_reference
before insert or update on public.meal_items
for each row execute function public.enforce_owned_reference();

revoke all on function public.enforce_owned_reference() from public, anon, authenticated;
