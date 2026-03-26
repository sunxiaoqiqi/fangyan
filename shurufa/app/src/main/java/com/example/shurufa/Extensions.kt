package com.example.shurufa

import android.widget.TextView

fun TextView.scrollToBottom() {
    val scrollAmount = this.lineCount * this.lineHeight - this.height + this.paddingTop + this.paddingBottom
    if (scrollAmount > 0) {
        this.scrollTo(0, scrollAmount)
    }
}
