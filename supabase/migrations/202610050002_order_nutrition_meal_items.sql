alter table public.meal_items
add column position integer;

with ordered_items as (
  select
    id,
    row_number() over (
      partition by meal_id
      order by created_at, id
    ) - 1 as position
  from public.meal_items
)
update public.meal_items as meal_item
set position = ordered_items.position
from ordered_items
where ordered_items.id = meal_item.id;

alter table public.meal_items
alter column position set default 0,
alter column position set not null;

create unique index meal_items_meal_position_idx
on public.meal_items (meal_id, position);

create or replace function public.assign_meal_item_position()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if exists (
    select 1
    from public.meal_items
    where meal_id = new.meal_id
      and position = new.position
  ) then
    select coalesce(max(position) + 1, 0)
    into new.position
    from public.meal_items
    where meal_id = new.meal_id;
  end if;

  return new;
end;
$$;

create trigger meal_items_assign_position
before insert on public.meal_items
for each row execute function public.assign_meal_item_position();
