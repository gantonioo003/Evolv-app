# Evolv

Evolv is a mobile application concept for long-term workout and nutrition planning. The project focuses on consistency, simple daily guidance, and controlled adjustments based on user feedback and routine changes.

The goal is not to generate a new plan every week. Evolv is designed to maintain a stable plan over time and only adjust what is necessary when the user requests it or when there is enough context to justify a change.

## Product Vision

Most fitness apps either focus on workout tracking, calorie counting, or generic AI conversations. Evolv aims to combine workout planning, nutrition guidance, routine management, and an AI assistant in a way that does not overwhelm the user.

The central idea is simple:

> Organize the user's real fitness routine without constantly disrupting the plan.

## Core Principles

- The plan should be stable by default.
- Adjustments should be small, intentional, and explainable.
- The user should not be forced to log everything every day.
- Workout, diet, and routine should be connected through one assistant.
- The app should support both light users and detailed users.
- Workout, diet, Coach, reminders, and load tracking should work independently.
- The app should not ask users to choose a usage mode or infer one from their behavior.
- Every main feature remains available to every user.
- Onboarding covers the complete setup, but optional steps can be skipped and completed later in profile settings.
- The daily experience should be simple and low-friction.

## MVP Scope

The first version of Evolv will focus on validating the core experience.

### Included in the MVP

- User account and authentication.
- Complete onboarding flow with skippable optional steps.
- Initial workout plan.
- Simple nutrition plan.
- Today screen with a daily summary.
- Workout screen with weekly structure and exercises.
- Diet screen with meals and substitutions.
- Structured food catalog with calories, macros, portions, and expandable micronutrients.
- Optional daily nutrition totals and estimated energy expenditure.
- Exercise catalog covering machines, free weights, cables, bodyweight, calisthenics, and power training.
- Optional training preferences that guide recommendations without hiding the full catalog.
- Single AI assistant called Coach Evolv.
- Coach Evolv for questions, explanations, learning, and routine adjustments.
- Optional conversation memory to improve future guidance.
- Basic planner rules for routine adjustments.
- Notifications for workout and meal reminders.
- Account screen with settings and progress access.
- Standalone exercise load history and simple progression suggestions.

### Not included in the first MVP

- Image analysis.
- Food scanner.
- Wearable integrations.
- Advanced charts.
- Payment or subscriptions.
- Custom-trained AI model.
- Complex calendar integrations.
- Fully advanced nutrition calculations.

## Main Screens

### Today

The Today screen is the center of the app. It shows what is planned for the day without forcing the user to confirm actions.

It includes:

- Planned workout.
- Main meals for the day.
- Relevant reminders.
- Simple weekly context.
- Access to Coach Evolv through the navigation bar.

The Today screen should not pressure the user with mandatory actions such as "start workout" or "I will not train today". If the user wants to adjust something, they can open the Coach.

### Workout

The Workout screen shows the current weekly plan and the details of the selected training day.

It includes:

- Weekly training calendar.
- Active training plan.
- Exercises, sets, reps, rest, and optional load.
- Basic progression context.
- Quick load editing and history for each exercise.
- Clear suggestions showing when to increase and the next load to try.
- Access to Coach Evolv for adjustments.

### Diet

The Diet screen shows a simple and practical nutrition plan.

It includes:

- Daily meals.
- Approximate calorie and protein targets.
- Simple food substitutions.
- Access to Coach Evolv for food swaps or routine issues.

### Coach Evolv

Coach Evolv is a single AI assistant used across the app. It is not limited to routine adjustments. The user can also use it to ask questions, understand training and nutrition concepts, learn why something is in the plan, and get practical explanations.

It can be accessed from Today, Workout, or Diet. The assistant remains the same, but the initial context changes depending on where the user opens it.

Examples:

- From Today: focus on the current day.
- From Workout: focus on training, schedule, exercises, and loads.
- From Diet: focus on meals, substitutions, and nutrition preferences.

Coach Evolv may also keep optional conversation memory, if the user allows it. This memory can help the assistant remember preferences, recurring doubts, disliked foods, training limitations, and past adjustments. The user should be able to review or disable this behavior later.

### Account

The Account screen works as the settings and profile hub.

It includes:

- Profile information.
- Current goal.
- Routine preferences.
- Notifications.
- Restrictions.
- Food preferences.
- Progress and history.
- Privacy and data options.
- Coach memory and conversation preferences.
- Future integrations.

Progress is not a main tab in the MVP. It is accessed through the Account screen.

## Planned Technical Stack

### Mobile

React Native with Expo.

### Backend

Node.js with TypeScript and NestJS.

### Database

Supabase with PostgreSQL.

### AI

OpenAI API or Gemini API.

### Notifications

Expo Notifications.

## Planned Architecture

The app will be divided into three main parts:

- Mobile application: user interface and mobile experience.
- Backend API: business rules, planner logic, authentication flow, and AI integration.
- Database: user profile, goals, workout plans, diet plans, history, and preferences.
- Optional Coach memory: relevant conversation context, user preferences, and recurring topics.

The AI assistant should not directly change the database without rules. It should interpret the user's request and call internal backend actions. The Planner module will be responsible for applying changes safely.

## Planner Concept

The Planner is an internal backend module responsible for applying rules to the user's plan.

Responsibilities:

- Build the weekly workout structure.
- Keep the long-term plan stable.
- Move workouts when requested.
- Avoid unnecessary changes.
- Apply basic progression rules.
- Store relevant routine adjustments.

In short:

- Coach Evolv understands and communicates.
- Planner applies rules and organizes the plan.
- Database stores the user's history and preferences.
- Optional memory stores useful context only when it improves the user experience and respects privacy settings.

## Current Project Status

Product definition and the MVP database phase are complete. The Supabase project is deployed, seeded, secured, and tested. Mobile and backend implementation have not started yet.

Completed so far:

- Initial product idea.
- MVP scope definition.
- User flow definition.
- Main screen structure.
- Visual direction concept.
- Documentation files.
- Project base documentation.
- Product and screen specification.
- Initial database schema.
- Supabase migration structure.
- Database documentation.
- Remote Supabase migrations and seed.
- Row Level Security and cross-user ownership protection.
- Transactional CRUD tests for workout, load, diet, Coach, and progress.
- Generated TypeScript database types.

Next steps:

1. Create the Expo mobile project.
2. Create the NestJS backend project.
3. Connect the application layers to Supabase.
4. Implement the Planner without AI.
5. Integrate the AI assistant.
6. Add notifications.
7. Prepare a portfolio-ready demo.

## Repository Structure

Expected structure:

```txt
evolv-app/
  docs/
    project documents, flow images, and visual concepts
    product and screen specifications
    database specification
  supabase/
    database migrations, generated types, tests, and Supabase notes
  mobile/
    React Native / Expo app
  backend/
    NestJS API
  README.md
```

This structure may evolve as the implementation begins.

## Author

Developed as a personal learning and portfolio project focused on mobile development, backend architecture, product design, and AI integration.
