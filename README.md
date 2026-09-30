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
- Proactive guidance should be quiet by default, rare, explainable, and dismissible.
- Dismissing an insight should silence repeated alerts about the same topic for a meaningful period.

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
- Local NLP pipeline with a small domain language model.
- Retrieval from a curated training and nutrition knowledge base.
- Basic planner rules for routine adjustments.
- Notifications for workout and meal reminders.
- Account screen with settings and progress access.
- Standalone exercise load history and simple progression suggestions.
- Optional nutrition-phase history for mass gain, fat loss, maintenance, recomposition, and diet breaks.
- Training plans that support Full body, Upper/Lower, Push/Pull/Legs, body-part, hybrid, and custom splits.
- Optional motivation and recovery check-ins used as context, never as mandatory daily tasks.
- Plateau signals that connect comparable exercise logs with nutrition and recovery context before suggesting a review.

### Not included in the first MVP

- Image analysis.
- Food scanner.
- Wearable integrations.
- Advanced charts.
- Payment or subscriptions.
- General-purpose language model comparable to commercial assistants.
- Dependence on paid or external language-model APIs.
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

Local NLP and machine learning service built with Python, PyTorch, scikit-learn, and FastAPI.

The first version will combine:

- A TF-IDF and logistic-regression baseline for intent classification.
- Local retrieval from a curated knowledge base.
- A small decoder-only Transformer language model trained from scratch for the Evolv domain.
- Confidence rules that ask for clarification when a request is uncertain.

### Notifications

Expo Notifications.

## Planned Architecture

The app will be divided into four main parts:

- Mobile application: user interface and mobile experience.
- Backend API: business rules, planner logic, authentication flow, and orchestration.
- Database: user profile, goals, workout plans, diet plans, history, and preferences.
- Local ML service: NLP, knowledge retrieval, intent classification, and response generation.
- Optional Coach memory: relevant conversation context, user preferences, and recurring topics.

The Coach should not directly change the database. It interprets the user's request, answers from the local knowledge base, and proposes structured actions. The NestJS backend validates those actions, and the Planner module applies allowed changes safely.

The local model is intentionally limited. The goal is to build and evaluate a real NLP and language-model pipeline that can run with free tools on personal hardware, not to reproduce the quality of a commercial general-purpose assistant.

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

Product definition and the initial MVP database phase are complete. The repository-side mobile phase is almost complete, with only validation on a physical iPhone still pending. All four backend passes are complete and provide authenticated integration between Expo, NestJS, and the remote Supabase project.

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
- Expo project with React Native and TypeScript.
- Five-tab navigation: Today, Workout, Coach, Diet, and Account.
- Login and skippable onboarding flows.
- Account-based Progress screen.
- Reusable visual components and centralized theme.
- Simulated load editing, progression guidance, meal logging, and Coach conversation.
- TypeScript, ESLint, web export, and manual navigation checks.
- NestJS backend project organized by initial modules.
- Environment validation, Supabase connection, token authentication, and centralized API errors.
- Initial health and authenticated profile endpoints.
- Backend build, unit test, and integration test passing.
- Authenticated goals, workout, load history, nutrition, and progress modules.
- Optional nutrition totals and user-controlled progression decisions.
- Remote migration applied for nutrition phases, training splits, readiness, and quiet insight preferences.
- Supabase Auth session, protected tabs, and authenticated API client in Expo.
- Real profile, goal, workout, nutrition, load, and progress flows connected to the mobile screens.
- Automatic profile creation enabled for new Auth accounts.
- Remote schema lint and transactional database tests passing.
- Database types regenerated from the updated remote schema.
- OpenAPI/Swagger documentation with Bearer authentication.
- Rate limiting, request timeout, request IDs, and structured HTTP logs.
- Separate API liveness and Supabase readiness checks.
- Eight unit tests and five E2E tests passing.
- Production dependency audit with no known vulnerabilities.

Next steps:

1. Implement the Planner without the Coach model.
2. Build the local NLP baseline and knowledge retrieval.
3. Train and evaluate the small Transformer language model.
4. Integrate the local Coach service.
5. Add notifications and validate the app on a physical iPhone.
6. Configure deployment and production environments.
7. Prepare a portfolio-ready demo.

## Repository Structure

Expected structure:

```txt
evolv-app/
  docs/
    project documents, flow images, and visual concepts
    product and screen specifications
    database specification
    mobile implementation notes
  supabase/
    database migrations, generated types, tests, and Supabase notes
  mobile/
    React Native / Expo app
  backend/
    NestJS API
  ml/
    local NLP, retrieval, training, evaluation, and model serving
  README.md
```

The mobile folder is connected to the real API and awaits physical iPhone validation. The backend MVP is complete for authentication, profiles, goals, workouts, loads, nutrition, and progress. The ML folder will be created when the local Coach phase begins.

## Author

Developed as a personal learning and portfolio project focused on mobile development, backend architecture, data engineering, NLP, machine learning, language models, and product design.
