export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      coach_conversations: {
        Row: {
          created_at: string
          entry_context: string | null
          id: string
          title: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          entry_context?: string | null
          id?: string
          title?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          entry_context?: string | null
          id?: string
          title?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      coach_memory_items: {
        Row: {
          category: string
          content: string
          created_at: string
          id: string
          is_active: boolean
          source_message_id: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          category: string
          content: string
          created_at?: string
          id?: string
          is_active?: boolean
          source_message_id?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          category?: string
          content?: string
          created_at?: string
          id?: string
          is_active?: boolean
          source_message_id?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "coach_memory_items_source_message_id_fkey"
            columns: ["source_message_id"]
            isOneToOne: false
            referencedRelation: "coach_messages"
            referencedColumns: ["id"]
          },
        ]
      }
      coach_messages: {
        Row: {
          content: string
          conversation_id: string
          created_at: string
          id: string
          metadata: Json
          role: Database["public"]["Enums"]["coach_message_role"]
          user_id: string
        }
        Insert: {
          content: string
          conversation_id: string
          created_at?: string
          id?: string
          metadata?: Json
          role: Database["public"]["Enums"]["coach_message_role"]
          user_id: string
        }
        Update: {
          content?: string
          conversation_id?: string
          created_at?: string
          id?: string
          metadata?: Json
          role?: Database["public"]["Enums"]["coach_message_role"]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "coach_messages_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "coach_conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      diet_plans: {
        Row: {
          created_at: string
          daily_calories_target: number | null
          daily_carbohydrate_target_g: number | null
          daily_fat_target_g: number | null
          daily_fiber_target_g: number | null
          daily_protein_target_g: number | null
          goal_id: string | null
          id: string
          name: string
          notes: string | null
          status: Database["public"]["Enums"]["plan_status"]
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          daily_calories_target?: number | null
          daily_carbohydrate_target_g?: number | null
          daily_fat_target_g?: number | null
          daily_fiber_target_g?: number | null
          daily_protein_target_g?: number | null
          goal_id?: string | null
          id?: string
          name: string
          notes?: string | null
          status?: Database["public"]["Enums"]["plan_status"]
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          daily_calories_target?: number | null
          daily_carbohydrate_target_g?: number | null
          daily_fat_target_g?: number | null
          daily_fiber_target_g?: number | null
          daily_protein_target_g?: number | null
          goal_id?: string | null
          id?: string
          name?: string
          notes?: string | null
          status?: Database["public"]["Enums"]["plan_status"]
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "diet_plans_goal_id_fkey"
            columns: ["goal_id"]
            isOneToOne: false
            referencedRelation: "goals"
            referencedColumns: ["id"]
          },
        ]
      }
      energy_expenditure_logs: {
        Row: {
          calories_kcal: number
          created_at: string
          description: string | null
          id: string
          occurred_at: string
          source: string
          user_id: string
        }
        Insert: {
          calories_kcal: number
          created_at?: string
          description?: string | null
          id?: string
          occurred_at?: string
          source: string
          user_id: string
        }
        Update: {
          calories_kcal?: number
          created_at?: string
          description?: string | null
          id?: string
          occurred_at?: string
          source?: string
          user_id?: string
        }
        Relationships: []
      }
      equipment: {
        Row: {
          category: string
          created_at: string
          id: string
          name: string
          slug: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: string
          name: string
          slug: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: string
          name?: string
          slug?: string
        }
        Relationships: []
      }
      exercise_equipment: {
        Row: {
          equipment_id: string
          exercise_id: string
          is_required: boolean
        }
        Insert: {
          equipment_id: string
          exercise_id: string
          is_required?: boolean
        }
        Update: {
          equipment_id?: string
          exercise_id?: string
          is_required?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "exercise_equipment_equipment_id_fkey"
            columns: ["equipment_id"]
            isOneToOne: false
            referencedRelation: "equipment"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exercise_equipment_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
        ]
      }
      exercise_logs: {
        Row: {
          created_at: string
          exercise_id: string
          id: string
          load_kg: number | null
          notes: string | null
          performed_at: string
          reps_summary: string | null
          sets_completed: number | null
          user_id: string
          workout_log_id: string | null
        }
        Insert: {
          created_at?: string
          exercise_id: string
          id?: string
          load_kg?: number | null
          notes?: string | null
          performed_at?: string
          reps_summary?: string | null
          sets_completed?: number | null
          user_id: string
          workout_log_id?: string | null
        }
        Update: {
          created_at?: string
          exercise_id?: string
          id?: string
          load_kg?: number | null
          notes?: string | null
          performed_at?: string
          reps_summary?: string | null
          sets_completed?: number | null
          user_id?: string
          workout_log_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "exercise_logs_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exercise_logs_workout_log_id_fkey"
            columns: ["workout_log_id"]
            isOneToOne: false
            referencedRelation: "workout_logs"
            referencedColumns: ["id"]
          },
        ]
      }
      exercise_muscles: {
        Row: {
          exercise_id: string
          muscle_group_id: string
          role: string
        }
        Insert: {
          exercise_id: string
          muscle_group_id: string
          role: string
        }
        Update: {
          exercise_id?: string
          muscle_group_id?: string
          role?: string
        }
        Relationships: [
          {
            foreignKeyName: "exercise_muscles_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exercise_muscles_muscle_group_id_fkey"
            columns: ["muscle_group_id"]
            isOneToOne: false
            referencedRelation: "muscle_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      exercise_progression_suggestions: {
        Row: {
          accepted_at: string | null
          created_at: string
          current_load_kg: number
          dismissed_at: string | null
          exercise_id: string
          id: string
          reason: string
          suggested_for: string | null
          suggested_load_kg: number
          user_id: string
        }
        Insert: {
          accepted_at?: string | null
          created_at?: string
          current_load_kg: number
          dismissed_at?: string | null
          exercise_id: string
          id?: string
          reason: string
          suggested_for?: string | null
          suggested_load_kg: number
          user_id: string
        }
        Update: {
          accepted_at?: string | null
          created_at?: string
          current_load_kg?: number
          dismissed_at?: string | null
          exercise_id?: string
          id?: string
          reason?: string
          suggested_for?: string | null
          suggested_load_kg?: number
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "exercise_progression_suggestions_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
        ]
      }
      exercise_substitutions: {
        Row: {
          compatibility: number
          exercise_id: string
          reason: string | null
          substitute_exercise_id: string
        }
        Insert: {
          compatibility?: number
          exercise_id: string
          reason?: string | null
          substitute_exercise_id: string
        }
        Update: {
          compatibility?: number
          exercise_id?: string
          reason?: string | null
          substitute_exercise_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "exercise_substitutions_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exercise_substitutions_substitute_exercise_id_fkey"
            columns: ["substitute_exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
        ]
      }
      exercise_training_styles: {
        Row: {
          exercise_id: string
          training_style_id: string
        }
        Insert: {
          exercise_id: string
          training_style_id: string
        }
        Update: {
          exercise_id?: string
          training_style_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "exercise_training_styles_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exercise_training_styles_training_style_id_fkey"
            columns: ["training_style_id"]
            isOneToOne: false
            referencedRelation: "training_styles"
            referencedColumns: ["id"]
          },
        ]
      }
      exercises: {
        Row: {
          aliases: string[]
          created_at: string
          difficulty: string | null
          equipment: string | null
          external_id: string | null
          id: string
          instructions: string | null
          instructions_source_url: string | null
          is_compound: boolean
          is_system: boolean
          movement_pattern: string | null
          muscle_group: string
          name: string
          parent_exercise_id: string | null
          source: string
          updated_at: string
        }
        Insert: {
          aliases?: string[]
          created_at?: string
          difficulty?: string | null
          equipment?: string | null
          external_id?: string | null
          id?: string
          instructions?: string | null
          instructions_source_url?: string | null
          is_compound?: boolean
          is_system?: boolean
          movement_pattern?: string | null
          muscle_group: string
          name: string
          parent_exercise_id?: string | null
          source?: string
          updated_at?: string
        }
        Update: {
          aliases?: string[]
          created_at?: string
          difficulty?: string | null
          equipment?: string | null
          external_id?: string | null
          id?: string
          instructions?: string | null
          instructions_source_url?: string | null
          is_compound?: boolean
          is_system?: boolean
          movement_pattern?: string | null
          muscle_group?: string
          name?: string
          parent_exercise_id?: string | null
          source?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "exercises_parent_exercise_id_fkey"
            columns: ["parent_exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
        ]
      }
      food_log_items: {
        Row: {
          amount_grams: number | null
          calories_kcal: number
          carbohydrate_g: number
          created_at: string
          fat_g: number
          fiber_g: number
          food_id: string | null
          food_log_id: string
          food_name: string
          id: string
          protein_g: number
          quantity: number
          unit: string
          user_id: string
        }
        Insert: {
          amount_grams?: number | null
          calories_kcal?: number
          carbohydrate_g?: number
          created_at?: string
          fat_g?: number
          fiber_g?: number
          food_id?: string | null
          food_log_id: string
          food_name: string
          id?: string
          protein_g?: number
          quantity: number
          unit: string
          user_id: string
        }
        Update: {
          amount_grams?: number | null
          calories_kcal?: number
          carbohydrate_g?: number
          created_at?: string
          fat_g?: number
          fiber_g?: number
          food_id?: string | null
          food_log_id?: string
          food_name?: string
          id?: string
          protein_g?: number
          quantity?: number
          unit?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "food_log_items_food_id_fkey"
            columns: ["food_id"]
            isOneToOne: false
            referencedRelation: "foods"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "food_log_items_food_log_id_fkey"
            columns: ["food_log_id"]
            isOneToOne: false
            referencedRelation: "food_logs"
            referencedColumns: ["id"]
          },
        ]
      }
      food_logs: {
        Row: {
          created_at: string
          description: string | null
          id: string
          logged_at: string
          meal_name: string | null
          notes: string | null
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          logged_at?: string
          meal_name?: string | null
          notes?: string | null
          user_id: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          logged_at?: string
          meal_name?: string | null
          notes?: string | null
          user_id?: string
        }
        Relationships: []
      }
      food_nutrients: {
        Row: {
          amount: number
          data_quality: string | null
          food_id: string
          nutrient_id: string
        }
        Insert: {
          amount: number
          data_quality?: string | null
          food_id: string
          nutrient_id: string
        }
        Update: {
          amount?: number
          data_quality?: string | null
          food_id?: string
          nutrient_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "food_nutrients_food_id_fkey"
            columns: ["food_id"]
            isOneToOne: false
            referencedRelation: "foods"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "food_nutrients_nutrient_id_fkey"
            columns: ["nutrient_id"]
            isOneToOne: false
            referencedRelation: "nutrients"
            referencedColumns: ["id"]
          },
        ]
      }
      food_portions: {
        Row: {
          created_at: string
          food_id: string
          gram_weight: number | null
          id: string
          is_default: boolean
          name: string
          quantity: number
        }
        Insert: {
          created_at?: string
          food_id: string
          gram_weight?: number | null
          id?: string
          is_default?: boolean
          name: string
          quantity?: number
        }
        Update: {
          created_at?: string
          food_id?: string
          gram_weight?: number | null
          id?: string
          is_default?: boolean
          name?: string
          quantity?: number
        }
        Relationships: [
          {
            foreignKeyName: "food_portions_food_id_fkey"
            columns: ["food_id"]
            isOneToOne: false
            referencedRelation: "foods"
            referencedColumns: ["id"]
          },
        ]
      }
      foods: {
        Row: {
          barcode: string | null
          base_amount: number
          base_unit: string
          brand: string | null
          calories_kcal: number | null
          carbohydrate_g: number | null
          created_at: string
          data_type: string | null
          external_id: string | null
          fat_g: number | null
          fiber_g: number | null
          id: string
          is_verified: boolean
          last_synced_at: string | null
          locale: string
          name: string
          protein_g: number | null
          saturated_fat_g: number | null
          sodium_mg: number | null
          source: string
          sugar_g: number | null
          updated_at: string
          user_id: string | null
        }
        Insert: {
          barcode?: string | null
          base_amount?: number
          base_unit?: string
          brand?: string | null
          calories_kcal?: number | null
          carbohydrate_g?: number | null
          created_at?: string
          data_type?: string | null
          external_id?: string | null
          fat_g?: number | null
          fiber_g?: number | null
          id?: string
          is_verified?: boolean
          last_synced_at?: string | null
          locale?: string
          name: string
          protein_g?: number | null
          saturated_fat_g?: number | null
          sodium_mg?: number | null
          source?: string
          sugar_g?: number | null
          updated_at?: string
          user_id?: string | null
        }
        Update: {
          barcode?: string | null
          base_amount?: number
          base_unit?: string
          brand?: string | null
          calories_kcal?: number | null
          carbohydrate_g?: number | null
          created_at?: string
          data_type?: string | null
          external_id?: string | null
          fat_g?: number | null
          fiber_g?: number | null
          id?: string
          is_verified?: boolean
          last_synced_at?: string | null
          locale?: string
          name?: string
          protein_g?: number | null
          saturated_fat_g?: number | null
          sodium_mg?: number | null
          source?: string
          sugar_g?: number | null
          updated_at?: string
          user_id?: string | null
        }
        Relationships: []
      }
      goals: {
        Row: {
          created_at: string
          description: string | null
          id: string
          is_active: boolean
          target_date: string | null
          target_weight_kg: number | null
          title: string
          type: Database["public"]["Enums"]["goal_type"]
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          target_date?: string | null
          target_weight_kg?: number | null
          title: string
          type: Database["public"]["Enums"]["goal_type"]
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          target_date?: string | null
          target_weight_kg?: number | null
          title?: string
          type?: Database["public"]["Enums"]["goal_type"]
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      meal_items: {
        Row: {
          amount: string | null
          created_at: string
          food_id: string | null
          id: string
          meal_id: string
          name: string
          notes: string | null
          quantity: number | null
          substitution_group: string | null
          unit: string | null
        }
        Insert: {
          amount?: string | null
          created_at?: string
          food_id?: string | null
          id?: string
          meal_id: string
          name: string
          notes?: string | null
          quantity?: number | null
          substitution_group?: string | null
          unit?: string | null
        }
        Update: {
          amount?: string | null
          created_at?: string
          food_id?: string | null
          id?: string
          meal_id?: string
          name?: string
          notes?: string | null
          quantity?: number | null
          substitution_group?: string | null
          unit?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "meal_items_food_id_fkey"
            columns: ["food_id"]
            isOneToOne: false
            referencedRelation: "foods"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "meal_items_meal_id_fkey"
            columns: ["meal_id"]
            isOneToOne: false
            referencedRelation: "meals"
            referencedColumns: ["id"]
          },
        ]
      }
      meals: {
        Row: {
          calories_target: number | null
          carbohydrate_target_g: number | null
          created_at: string
          description: string | null
          diet_plan_id: string
          fat_target_g: number | null
          id: string
          meal_time: string | null
          name: string
          position: number
          protein_target_g: number | null
          updated_at: string
        }
        Insert: {
          calories_target?: number | null
          carbohydrate_target_g?: number | null
          created_at?: string
          description?: string | null
          diet_plan_id: string
          fat_target_g?: number | null
          id?: string
          meal_time?: string | null
          name: string
          position?: number
          protein_target_g?: number | null
          updated_at?: string
        }
        Update: {
          calories_target?: number | null
          carbohydrate_target_g?: number | null
          created_at?: string
          description?: string | null
          diet_plan_id?: string
          fat_target_g?: number | null
          id?: string
          meal_time?: string | null
          name?: string
          position?: number
          protein_target_g?: number | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "meals_diet_plan_id_fkey"
            columns: ["diet_plan_id"]
            isOneToOne: false
            referencedRelation: "diet_plans"
            referencedColumns: ["id"]
          },
        ]
      }
      muscle_groups: {
        Row: {
          body_region: string
          created_at: string
          id: string
          name: string
          slug: string
        }
        Insert: {
          body_region: string
          created_at?: string
          id?: string
          name: string
          slug: string
        }
        Update: {
          body_region?: string
          created_at?: string
          id?: string
          name?: string
          slug?: string
        }
        Relationships: []
      }
      nutrients: {
        Row: {
          category: string
          code: string
          created_at: string
          id: string
          name: string
          unit: string
        }
        Insert: {
          category: string
          code: string
          created_at?: string
          id?: string
          name: string
          unit: string
        }
        Update: {
          category?: string
          code?: string
          created_at?: string
          id?: string
          name?: string
          unit?: string
        }
        Relationships: []
      }
      planner_adjustments: {
        Row: {
          applied_at: string | null
          applied_change: Json | null
          conversation_id: string | null
          created_at: string
          id: string
          reason: string
          requested_change: Json
          status: Database["public"]["Enums"]["adjustment_status"]
          updated_at: string
          user_id: string
        }
        Insert: {
          applied_at?: string | null
          applied_change?: Json | null
          conversation_id?: string | null
          created_at?: string
          id?: string
          reason: string
          requested_change?: Json
          status?: Database["public"]["Enums"]["adjustment_status"]
          updated_at?: string
          user_id: string
        }
        Update: {
          applied_at?: string | null
          applied_change?: Json | null
          conversation_id?: string | null
          created_at?: string
          id?: string
          reason?: string
          requested_change?: Json
          status?: Database["public"]["Enums"]["adjustment_status"]
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "planner_adjustments_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "coach_conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          available_training_days: Database["public"]["Enums"]["weekday"][]
          birth_date: string | null
          coach_memory_enabled: boolean
          created_at: string
          current_weight_kg: number | null
          disliked_foods: string[]
          food_restrictions: string[]
          full_name: string | null
          height_cm: number | null
          id: string
          injuries_or_limitations: string[]
          notifications_enabled: boolean
          onboarding_status: string
          preferred_training_time: string | null
          training_level: string | null
          updated_at: string
        }
        Insert: {
          available_training_days?: Database["public"]["Enums"]["weekday"][]
          birth_date?: string | null
          coach_memory_enabled?: boolean
          created_at?: string
          current_weight_kg?: number | null
          disliked_foods?: string[]
          food_restrictions?: string[]
          full_name?: string | null
          height_cm?: number | null
          id: string
          injuries_or_limitations?: string[]
          notifications_enabled?: boolean
          onboarding_status?: string
          preferred_training_time?: string | null
          training_level?: string | null
          updated_at?: string
        }
        Update: {
          available_training_days?: Database["public"]["Enums"]["weekday"][]
          birth_date?: string | null
          coach_memory_enabled?: boolean
          created_at?: string
          current_weight_kg?: number | null
          disliked_foods?: string[]
          food_restrictions?: string[]
          full_name?: string | null
          height_cm?: number | null
          id?: string
          injuries_or_limitations?: string[]
          notifications_enabled?: boolean
          onboarding_status?: string
          preferred_training_time?: string | null
          training_level?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      progress_entries: {
        Row: {
          arm_cm: number | null
          chest_cm: number | null
          created_at: string
          id: string
          leg_cm: number | null
          measured_at: string
          notes: string | null
          user_id: string
          waist_cm: number | null
          weight_kg: number | null
        }
        Insert: {
          arm_cm?: number | null
          chest_cm?: number | null
          created_at?: string
          id?: string
          leg_cm?: number | null
          measured_at?: string
          notes?: string | null
          user_id: string
          waist_cm?: number | null
          weight_kg?: number | null
        }
        Update: {
          arm_cm?: number | null
          chest_cm?: number | null
          created_at?: string
          id?: string
          leg_cm?: number | null
          measured_at?: string
          notes?: string | null
          user_id?: string
          waist_cm?: number | null
          weight_kg?: number | null
        }
        Relationships: []
      }
      progress_photos: {
        Row: {
          created_at: string
          id: string
          photo_type: string | null
          progress_entry_id: string | null
          storage_path: string
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          photo_type?: string | null
          progress_entry_id?: string | null
          storage_path: string
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          photo_type?: string | null
          progress_entry_id?: string | null
          storage_path?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "progress_photos_progress_entry_id_fkey"
            columns: ["progress_entry_id"]
            isOneToOne: false
            referencedRelation: "progress_entries"
            referencedColumns: ["id"]
          },
        ]
      }
      training_preferences: {
        Row: {
          avoided_exercises: string[]
          created_at: string
          notes: string | null
          preferred_equipment_categories: string[]
          updated_at: string
          user_id: string
        }
        Insert: {
          avoided_exercises?: string[]
          created_at?: string
          notes?: string | null
          preferred_equipment_categories?: string[]
          updated_at?: string
          user_id: string
        }
        Update: {
          avoided_exercises?: string[]
          created_at?: string
          notes?: string | null
          preferred_equipment_categories?: string[]
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      training_styles: {
        Row: {
          created_at: string
          id: string
          name: string
          slug: string
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
          slug: string
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
          slug?: string
        }
        Relationships: []
      }
      user_available_equipment: {
        Row: {
          created_at: string
          equipment_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          equipment_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          equipment_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_available_equipment_equipment_id_fkey"
            columns: ["equipment_id"]
            isOneToOne: false
            referencedRelation: "equipment"
            referencedColumns: ["id"]
          },
        ]
      }
      user_preferred_training_styles: {
        Row: {
          created_at: string
          training_style_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          training_style_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          training_style_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_preferred_training_styles_training_style_id_fkey"
            columns: ["training_style_id"]
            isOneToOne: false
            referencedRelation: "training_styles"
            referencedColumns: ["id"]
          },
        ]
      }
      workout_day_exercises: {
        Row: {
          created_at: string
          exercise_id: string
          id: string
          max_reps: number
          min_reps: number
          notes: string | null
          position: number
          rest_seconds: number | null
          sets: number
          target_load_kg: number | null
          updated_at: string
          workout_day_id: string
        }
        Insert: {
          created_at?: string
          exercise_id: string
          id?: string
          max_reps: number
          min_reps: number
          notes?: string | null
          position?: number
          rest_seconds?: number | null
          sets: number
          target_load_kg?: number | null
          updated_at?: string
          workout_day_id: string
        }
        Update: {
          created_at?: string
          exercise_id?: string
          id?: string
          max_reps?: number
          min_reps?: number
          notes?: string | null
          position?: number
          rest_seconds?: number | null
          sets?: number
          target_load_kg?: number | null
          updated_at?: string
          workout_day_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "workout_day_exercises_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "exercises"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "workout_day_exercises_workout_day_id_fkey"
            columns: ["workout_day_id"]
            isOneToOne: false
            referencedRelation: "workout_days"
            referencedColumns: ["id"]
          },
        ]
      }
      workout_days: {
        Row: {
          created_at: string
          estimated_minutes: number | null
          focus: string
          id: string
          position: number
          title: string
          updated_at: string
          weekday: Database["public"]["Enums"]["weekday"]
          workout_plan_id: string
        }
        Insert: {
          created_at?: string
          estimated_minutes?: number | null
          focus: string
          id?: string
          position?: number
          title: string
          updated_at?: string
          weekday: Database["public"]["Enums"]["weekday"]
          workout_plan_id: string
        }
        Update: {
          created_at?: string
          estimated_minutes?: number | null
          focus?: string
          id?: string
          position?: number
          title?: string
          updated_at?: string
          weekday?: Database["public"]["Enums"]["weekday"]
          workout_plan_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "workout_days_workout_plan_id_fkey"
            columns: ["workout_plan_id"]
            isOneToOne: false
            referencedRelation: "workout_plans"
            referencedColumns: ["id"]
          },
        ]
      }
      workout_logs: {
        Row: {
          created_at: string
          id: string
          notes: string | null
          performed_at: string
          user_id: string
          workout_day_id: string | null
        }
        Insert: {
          created_at?: string
          id?: string
          notes?: string | null
          performed_at?: string
          user_id: string
          workout_day_id?: string | null
        }
        Update: {
          created_at?: string
          id?: string
          notes?: string | null
          performed_at?: string
          user_id?: string
          workout_day_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "workout_logs_workout_day_id_fkey"
            columns: ["workout_day_id"]
            isOneToOne: false
            referencedRelation: "workout_days"
            referencedColumns: ["id"]
          },
        ]
      }
      workout_plans: {
        Row: {
          created_at: string
          end_date: string | null
          goal_id: string | null
          id: string
          name: string
          notes: string | null
          start_date: string
          status: Database["public"]["Enums"]["plan_status"]
          updated_at: string
          user_id: string
          weekly_frequency: number
        }
        Insert: {
          created_at?: string
          end_date?: string | null
          goal_id?: string | null
          id?: string
          name: string
          notes?: string | null
          start_date: string
          status?: Database["public"]["Enums"]["plan_status"]
          updated_at?: string
          user_id: string
          weekly_frequency: number
        }
        Update: {
          created_at?: string
          end_date?: string | null
          goal_id?: string | null
          id?: string
          name?: string
          notes?: string | null
          start_date?: string
          status?: Database["public"]["Enums"]["plan_status"]
          updated_at?: string
          user_id?: string
          weekly_frequency?: number
        }
        Relationships: [
          {
            foreignKeyName: "workout_plans_goal_id_fkey"
            columns: ["goal_id"]
            isOneToOne: false
            referencedRelation: "goals"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      adjustment_status: "pending" | "applied" | "rejected"
      coach_message_role: "user" | "assistant" | "system"
      goal_type:
        | "hypertrophy"
        | "fat_loss"
        | "strength"
        | "health"
        | "recomposition"
        | "maintenance"
      plan_status: "draft" | "active" | "archived"
      weekday:
        | "monday"
        | "tuesday"
        | "wednesday"
        | "thursday"
        | "friday"
        | "saturday"
        | "sunday"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      adjustment_status: ["pending", "applied", "rejected"],
      coach_message_role: ["user", "assistant", "system"],
      goal_type: [
        "hypertrophy",
        "fat_loss",
        "strength",
        "health",
        "recomposition",
        "maintenance",
      ],
      plan_status: ["draft", "active", "archived"],
      weekday: [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
      ],
    },
  },
} as const
