import {
  BadRequestException,
  Injectable,
  NotFoundException,
  UnprocessableEntityException,
} from '@nestjs/common';
import type { Tables, TablesInsert } from '../database/database.types.js';
import { throwDatabaseError } from '../common/errors/database.error.js';
import { SupabaseService } from '../supabase/supabase.service.js';
import type { CreateFoodLogDto } from './dto/create-food-log.dto.js';
import type { CreateFoodLogItemDto } from './dto/create-food-log-item.dto.js';
import type { NutritionLogsQueryDto } from './dto/nutrition-logs-query.dto.js';
import type { SetPlannedMealRegistrationDto } from './dto/set-planned-meal-registration.dto.js';
import { calculateNutritionSummary } from './nutrition-summary.js';

type FoodLog = Tables<'food_logs'>;
type FoodLogItem = Tables<'food_log_items'>;

@Injectable()
export class NutritionService {
  constructor(private readonly supabase: SupabaseService) {}

  async getActivePlan(userId: string, accessToken: string) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('diet_plans')
      .select(
        `
        *,
        goals (*),
        meals (
          *,
          meal_items (
            *,
            foods (id, name, brand, calories_kcal, protein_g, carbohydrate_g, fat_g, fiber_g)
          )
        )
      `,
      )
      .eq('user_id', userId)
      .eq('status', 'active')
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'NutritionService.getActivePlan',
        error,
        'Nao foi possivel buscar o plano alimentar.',
      );
    }
    if (!data) return null;

    data.meals.sort((a, b) => a.position - b.position);
    return data;
  }

  async listLogs(
    userId: string,
    accessToken: string,
    queryDto: NutritionLogsQueryDto,
  ) {
    let query = this.supabase
      .forUser(accessToken)
      .from('food_logs')
      .select('*, food_log_items (*)')
      .eq('user_id', userId)
      .order('logged_at', { ascending: false })
      .limit(queryDto.limit);

    if (queryDto.from) query = query.gte('logged_at', queryDto.from);
    if (queryDto.to) query = query.lt('logged_at', queryDto.to);

    const { data, error } = await query;
    if (error) {
      throwDatabaseError(
        'NutritionService.listLogs',
        error,
        'Nao foi possivel buscar os registros alimentares.',
      );
    }
    return data;
  }

  async getSummary(
    userId: string,
    accessToken: string,
    queryDto: NutritionLogsQueryDto,
  ) {
    const logs = await this.listLogs(userId, accessToken, {
      from: queryDto.from,
      to: queryDto.to,
      limit: Math.min(queryDto.limit, 100),
    });
    const items = logs.flatMap((log) => log.food_log_items);
    return calculateNutritionSummary(items);
  }

  async createLog(
    userId: string,
    accessToken: string,
    dto: CreateFoodLogDto,
  ): Promise<FoodLog> {
    const input: TablesInsert<'food_logs'> = {
      user_id: userId,
      logged_at: dto.logged_at,
      description: dto.description,
      meal_name: dto.meal_name,
      notes: dto.notes,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('food_logs')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'NutritionService.createLog',
        error,
        'Nao foi possivel criar o registro alimentar.',
      );
    }
    return data;
  }

  async addItem(
    userId: string,
    accessToken: string,
    foodLogId: string,
    dto: CreateFoodLogItemDto,
  ): Promise<FoodLogItem> {
    const input: TablesInsert<'food_log_items'> = {
      food_log_id: foodLogId,
      user_id: userId,
      food_id: dto.food_id,
      food_name: dto.food_name,
      quantity: dto.quantity,
      unit: dto.unit,
      amount_grams: dto.amount_grams,
      calories_kcal: dto.calories_kcal,
      protein_g: dto.protein_g,
      carbohydrate_g: dto.carbohydrate_g,
      fat_g: dto.fat_g,
      fiber_g: dto.fiber_g,
    };
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('food_log_items')
      .insert(input)
      .select('*')
      .single();

    if (error) {
      throwDatabaseError(
        'NutritionService.addItem',
        error,
        'Nao foi possivel adicionar o alimento.',
      );
    }
    return data;
  }

  async setPlannedMealRegistration(
    accessToken: string,
    mealId: string,
    dto: SetPlannedMealRegistrationDto,
  ) {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .rpc('set_planned_meal_registration', {
        p_meal_id: mealId,
        p_local_date: dto.local_date,
        p_logged_at: dto.logged_at,
        p_registered: dto.registered,
      });
    if (error?.message === 'PLANNED_MEAL_NOT_FOUND') {
      throw new NotFoundException('Esta refeição não está no seu plano ativo.');
    }
    if (error?.message === 'MEAL_PORTIONS_UNAVAILABLE') {
      throw new UnprocessableEntityException(
        'Esta refeição ainda não tem porções e macros completos para o balanço.',
      );
    }
    if (error?.message === 'INVALID_MEAL_REGISTRATION') {
      throw new BadRequestException('Não consegui identificar a data do registro.');
    }
    if (error) {
      throwDatabaseError(
        'NutritionService.setPlannedMealRegistration',
        error,
        'Não foi possível atualizar a refeição.',
      );
    }
    return { registered: data };
  }

  async removeLog(
    userId: string,
    accessToken: string,
    foodLogId: string,
  ): Promise<{ id: string }> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('food_logs')
      .delete()
      .eq('id', foodLogId)
      .eq('user_id', userId)
      .select('id')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'NutritionService.removeLog',
        error,
        'Nao foi possivel remover o registro alimentar.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'FOOD_LOG_NOT_FOUND',
        message: 'Registro alimentar nao encontrado.',
      });
    }
    return data;
  }

  async removeItem(
    userId: string,
    accessToken: string,
    itemId: string,
  ): Promise<{ id: string }> {
    const { data, error } = await this.supabase
      .forUser(accessToken)
      .from('food_log_items')
      .delete()
      .eq('id', itemId)
      .eq('user_id', userId)
      .select('id')
      .maybeSingle();

    if (error) {
      throwDatabaseError(
        'NutritionService.removeItem',
        error,
        'Nao foi possivel remover o alimento.',
      );
    }
    if (!data) {
      throw new NotFoundException({
        code: 'FOOD_LOG_ITEM_NOT_FOUND',
        message: 'Alimento registrado nao encontrado.',
      });
    }
    return data;
  }
}
