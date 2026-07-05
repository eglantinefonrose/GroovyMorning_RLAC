package com.gmfm.radiofrance.data

import android.content.Context
import android.content.SharedPreferences
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PreferencesManager @Inject constructor(
    @ApplicationContext context: Context
) {
    private val sharedPreferences: SharedPreferences =
        context.getSharedPreferences("gmfm_prefs", Context.MODE_PRIVATE)

    var isFirstVisit: Boolean
        get() = sharedPreferences.getBoolean(KEY_IS_FIRST_VISIT, true)
        set(value) = sharedPreferences.edit().putBoolean(KEY_IS_FIRST_VISIT, value).apply()

    companion object {
        private const val KEY_IS_FIRST_VISIT = "is_first_visit"
    }
}
