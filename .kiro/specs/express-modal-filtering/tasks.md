# Implementation Plan

- [x] 1. Create Express Search API Endpoint





  - [x] 1.1 Implement the `/api/express-search` POST endpoint in Dashboard.py


    - Add route handler that accepts JSON body with filter parameters
    - Parse and validate property_type, listing_type, price_min, price_max, features, limit, offset
    - Return 400 error for invalid parameters
    - _Requirements: 4.1, 4.2_
  - [x] 1.2 Implement the query filter builder function

    - Create `build_express_query(filters)` function that constructs parameterized SQL
    - Build WHERE clauses for property_type, listing_type, price range
    - Add JOIN with listing_features table for feature filtering
    - Return SQL string and parameter list

  - [ ]* 1.3 Write property test for database query correctness
    - **Property 2: Database query returns only matching results**
    - **Validates: Requirements 1.4, 2.2, 4.2**
  - [x] 1.4 Implement the count query for total results

    - Create separate COUNT query to get total matching listings
    - Return total_count in API response alongside limited results
    - _Requirements: 3.1, 3.3_

- [ ] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Update Frontend Filter State Management





  - [x] 3.1 Refactor express modal state to use centralized state object


    - Create `expressState` object with propertyType, listingType, priceMin, priceMax, features, results, totalCount, isLoading, error
    - Update existing functions to use centralized state
    - _Requirements: 1.1, 1.2_
  - [x] 3.2 Implement debounced API fetch function

    - Create `fetchExpressResults()` function that sends POST request to `/api/express-search`
    - Add 300ms debounce to prevent excessive API calls
    - Handle loading state and errors

  - [x] 3.3 Update filter change handlers to trigger API fetch

    - Modify `switchExpressType()`, `setExpressListingType()`, `updatePriceSlider()` to call debounced fetch
    - Update feature filter change handlers


- [x] 4. Implement Price Slider Validation





  - [x] 4.1 Add min/max constraint enforcement to price slider


    - Modify `updatePriceSlider()` to swap values if min > max
    - Update slider positions and display values accordingly

  - [ ]* 4.2 Write property test for price slider invariant
    - **Property 3: Price slider min/max invariant**
    - **Validates: Requirements 2.3**

- [x] 5. Update Results Preview Display





  - [x] 5.1 Implement `updateExpressPreview()` function


    - Accept results array and totalCount from API response
    - Render up to 5 listing preview items
    - Show count indicator when totalCount > 5
    - Show localized "no results" message when empty

  - [ ]* 5.2 Write property test for preview count behavior
    - **Property 4: Preview count behavior**
    - **Validates: Requirements 3.1, 3.3**
  - [ ]* 5.3 Write property test for preview item content
    - **Property 5: Preview items contain required information**
    - **Validates: Requirements 3.2**
  - [x] 5.4 Implement preview item click handler


    - Open edit modal for clicked listing
    - Close express modal


- [x] 6. Checkpoint - Ensure all tests pass






  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Feature Filter Updates





  - [x] 7.1 Update `updateExpressFeatures()` to work with API results



    - Modify function to populate feature options based on available values in filtered results
    - Preserve selected values when property type changes

  - [ ]* 7.2 Write property test for feature filter matching
    - **Property 1: Feature filters match property type**
    - **Validates: Requirements 1.2**

- [x] 8. Implement Language Support






  - [x] 8.1 Update preview rendering to use language-specific titles

    - Use title_ro or title_ru based on currentLanguage


  - [ ]* 8.2 Write property test for language-specific title display
    - **Property 6: Language-specific title display**
    - **Validates: Requirements 6.2**
  - [x] 8.3 Ensure all modal labels use translation system


    - Verify data-i18n attributes on all labels and buttons
    - Add any missing translation keys


- [x] 9. Implement Reset and Apply Functions





  - [x] 9.1 Update `resetExpressFilters()` function


    - Reset all state to defaults (apartment, for_sale, full price range)
    - Clear all feature selections
    - Trigger new API fetch with default filters

  - [x] 9.2 Update `applyExpressResults()` function


    - Apply property type and listing type to dashboard filters
    - Update dashboard dropdown UI
    - Trigger dashboard filter/sort function
    - Close express modal


- [ ] 10. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
