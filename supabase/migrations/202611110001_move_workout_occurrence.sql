-- Move a dated session using two calendar overrides, without editing the weekly template.
alter table public.planner_adjustments
  drop constraint planner_adjustments_adjustment_kind_check,
  add constraint planner_adjustments_adjustment_kind_check check (
    adjustment_kind is null or adjustment_kind in (
      'move_workout_day', 'move_workout_occurrence', 'replace_exercise', 'replace_meal_item', 'set_day_activity'
    )
  );

create or replace function public.mutate_coach_adjustment(
  p_adjustment_id uuid,
  p_conversation_id uuid,
  p_operation text,
  p_confirmed boolean
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current_item jsonb;
  v_expected jsonb;
  v_plan_status public.plan_status;
  v_swap_weekday public.weekday;
  v_origin_date date;
  v_target_date date;
  v_origin jsonb;
  v_destination jsonb;
  v_source_saved public.daily_activity_overrides%rowtype;
  v_target_saved public.daily_activity_overrides%rowtype;
  v_previous_scope text := current_setting('evolv.coach_adjustment', true);
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if p_confirmed is distinct from true
     or p_operation is null
     or p_operation not in ('apply', 'reject', 'revert') then
    raise exception 'Explicit confirmation is required' using errcode = '22023';
  end if;

  select * into v_adjustment
  from public.planner_adjustments
  where id = p_adjustment_id
    and user_id = v_user_id
    and conversation_id = p_conversation_id
    and source = 'coach'
  for update;

  if not found then
    raise exception 'Coach adjustment not found in this conversation' using errcode = 'P0002';
  end if;

  if p_operation = 'apply' then
    if v_adjustment.status <> 'pending' then
      raise exception 'Only pending adjustments can be applied' using errcode = '22023';
    end if;
    if v_adjustment.expires_at <= now() then
      raise exception 'Planner adjustment expired' using errcode = '40001';
    end if;
    v_expected := v_adjustment.before_snapshot;
  elsif p_operation = 'revert' then
    if v_adjustment.status <> 'applied' or v_adjustment.reverted_at is not null or not v_adjustment.reversible then
      raise exception 'Planner adjustment cannot be reverted' using errcode = '22023';
    end if;
    v_expected := v_adjustment.after_snapshot;
  end if;

  if v_adjustment.adjustment_kind = 'move_workout_occurrence' and p_operation <> 'reject' then
    v_origin_date := (v_adjustment.before_snapshot ->> 'source_date')::date;
    v_target_date := (v_adjustment.before_snapshot ->> 'target_date')::date;
    if v_origin_date is null or v_target_date is null or v_origin_date = v_target_date
       or date_trunc('week', v_origin_date::timestamp) <> date_trunc('week', v_target_date::timestamp) then
      raise exception 'Invalid session dates' using errcode = '22023';
    end if;

    perform 1 from public.workout_plans
    where id = v_adjustment.workout_plan_id and user_id = v_user_id
      and (p_operation = 'revert' or (status = 'active'
        and start_date <= least(v_origin_date, v_target_date)
        and (end_date is null or end_date >= greatest(v_origin_date, v_target_date))))
    for update;
    if not found then
      raise exception 'Workout plan changed after preview' using errcode = '40001';
    end if;

    perform 1 from public.workout_days
    where workout_plan_id = v_adjustment.workout_plan_id order by id for update;
    perform 1 from public.daily_activity_overrides
    where user_id = v_user_id and activity_date in (v_origin_date, v_target_date)
    order by activity_date for update;
    perform set_config('evolv.coach_adjustment', p_adjustment_id::text, true);

    if p_operation = 'apply' then
      v_origin := public.get_daily_activity_context(v_origin_date);
      v_destination := public.get_daily_activity_context(v_target_date);
      if v_origin ->> 'source' is distinct from 'workout_plan'
         or v_origin ->> 'workout_day_id' is distinct from v_adjustment.target_id::text
         or v_destination ->> 'source' = 'override'
         or v_destination ->> 'source' = 'workout_plan'
         or not exists (
           select 1 from public.workout_days
           where id = v_adjustment.target_id and workout_plan_id = v_adjustment.workout_plan_id
         )
         or v_adjustment.after_snapshot #>> '{target,estimated_minutes}'
            is distinct from v_origin ->> 'estimated_minutes' then
        raise exception 'Workout calendar changed after preview' using errcode = '40001';
      end if;

      -- No upsert. A concurrent edit on either date must abort the whole move.
      begin
        insert into public.daily_activity_overrides (
          user_id, activity_date, activity_type, estimated_minutes, nutrition_day_type, source
        ) values (v_user_id, v_origin_date, 'rest', 0, 'rest_day', 'coach')
        returning * into v_source_saved;

        insert into public.daily_activity_overrides (
          user_id, activity_date, activity_type, intensity, estimated_minutes,
          workout_day_id, nutrition_day_type, source
        ) values (v_user_id, v_target_date, 'resistance', v_origin ->> 'intensity',
          (v_origin ->> 'estimated_minutes')::integer, v_adjustment.target_id, 'training_day', 'coach')
        returning * into v_target_saved;
      exception when unique_violation then
        raise exception 'Workout calendar changed after preview' using errcode = '40001';
      end;

      update public.planner_adjustments
      set status = 'applied', confirmed_at = now(), applied_at = now(),
          applied_change = jsonb_build_object('source', to_jsonb(v_source_saved), 'target', to_jsonb(v_target_saved))
      where id = p_adjustment_id;
    else
      select * into v_source_saved from public.daily_activity_overrides
      where user_id = v_user_id and activity_date = v_origin_date;
      select * into v_target_saved from public.daily_activity_overrides
      where user_id = v_user_id and activity_date = v_target_date;
      if to_jsonb(v_source_saved) is distinct from v_adjustment.applied_change -> 'source'
         or to_jsonb(v_target_saved) is distinct from v_adjustment.applied_change -> 'target' then
        raise exception 'Workout calendar changed after adjustment' using errcode = '40001';
      end if;
      delete from public.daily_activity_overrides
      where user_id = v_user_id and id in (v_source_saved.id, v_target_saved.id);
      update public.planner_adjustments set reverted_at = now(), updated_at = now()
      where id = p_adjustment_id;
    end if;

    perform set_config('evolv.coach_adjustment', coalesce(v_previous_scope, ''), true);
    return p_adjustment_id;
  end if;

  if p_operation <> 'reject' then
    case v_adjustment.adjustment_kind
      when 'replace_meal_item' then
        select dp.status into v_plan_status from public.diet_plans dp
        where dp.id = v_adjustment.diet_plan_id and dp.user_id = v_user_id
        for update;
        if not found or (p_operation = 'apply' and v_plan_status <> 'active') then
          raise exception 'Diet plan changed after preview' using errcode = '40001';
        end if;

        select to_jsonb(mi) into v_current_item
        from public.meal_items mi
        join public.meals m on m.id = mi.meal_id
        where mi.id = v_adjustment.target_id and m.diet_plan_id = v_adjustment.diet_plan_id
        for update of mi;
        if not found or not (v_current_item @> (v_expected - 'meal_item_id'))
           or (v_current_item -> 'substitutions') is distinct from (v_expected -> 'substitutions') then
          raise exception 'Meal item changed after preview or adjustment' using errcode = '40001';
        end if;
      when 'replace_exercise', 'move_workout_day' then
        select wp.status into v_plan_status from public.workout_plans wp
        where wp.id = v_adjustment.workout_plan_id and wp.user_id = v_user_id
        for update;
        if not found or (p_operation = 'apply' and v_plan_status <> 'active') then
          raise exception 'Workout plan changed after preview' using errcode = '40001';
        end if;

        if v_adjustment.adjustment_kind = 'replace_exercise' then
          perform 1 from public.workout_day_exercises wde
          join public.workout_days wd on wd.id = wde.workout_day_id
          where wde.id = v_adjustment.target_id and wd.workout_plan_id = v_adjustment.workout_plan_id
          for update of wde;
          if not found then
            raise exception 'Workout exercise changed after preview' using errcode = '40001';
          end if;
        else
          perform 1 from public.workout_days
          where workout_plan_id = v_adjustment.workout_plan_id
          order by id for update;
          if p_operation = 'revert' and v_expected ->> 'swap_day_id' is not null then
            select weekday into v_swap_weekday from public.workout_days
            where id = (v_expected ->> 'swap_day_id')::uuid
              and workout_plan_id = v_adjustment.workout_plan_id;
            if not found or v_swap_weekday::text is distinct from v_expected ->> 'swap_weekday' then
              raise exception 'Swap day changed after adjustment' using errcode = '40001';
            end if;
          end if;
        end if;
      when 'set_day_activity' then
        perform 1 from public.daily_activity_overrides
        where user_id = v_user_id
          and activity_date = (v_adjustment.after_snapshot ->> 'activity_date')::date
        for update;
      else
        raise exception 'Unsupported Coach adjustment' using errcode = '22023';
    end case;
  end if;

  perform set_config('evolv.coach_adjustment', p_adjustment_id::text, true);
  if p_operation = 'reject' then
    perform public.reject_planner_adjustment(p_adjustment_id);
  elsif p_operation = 'apply' then
    if v_adjustment.adjustment_kind = 'set_day_activity' then
      perform public.apply_day_activity_adjustment(p_adjustment_id);
    else
      perform public.apply_planner_adjustment(p_adjustment_id);
    end if;
  elsif v_adjustment.adjustment_kind = 'set_day_activity' then
    perform public.revert_day_activity_adjustment(p_adjustment_id);
  else
    perform public.revert_planner_adjustment(p_adjustment_id);
    if v_adjustment.adjustment_kind = 'replace_meal_item'
       and v_adjustment.before_snapshot ? 'substitution_group' then
      update public.meal_items
      set substitution_group = v_adjustment.before_snapshot ->> 'substitution_group'
      where id = v_adjustment.target_id;
    end if;
  end if;
  perform set_config('evolv.coach_adjustment', coalesce(v_previous_scope, ''), true);
  return p_adjustment_id;
end;
$$;

revoke all on function public.mutate_coach_adjustment(uuid, uuid, text, boolean) from public;
grant execute on function public.mutate_coach_adjustment(uuid, uuid, text, boolean) to authenticated;
