package tech.layla.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Code
import androidx.compose.material.icons.outlined.GpsFixed
import androidx.compose.material.icons.outlined.Palette
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.SmartToy
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

internal val Ink = Color(0xFF000000)
internal val Card = Color(0xFF1C1C1E)
internal val Raised = Color(0xFF2C2C2E)
internal val Line = Color(0xFF3A3A3C)
internal val Blue = Color(0xFF0A84FF)
internal val Muted = Color(0xFF8E8E93)
internal val Soft = Color(0xFFD1D1D6)
internal val Danger = Color(0xFFFF453A)

internal fun domainColor(slug: String) = when (slug) {
    "code" -> Color(0xFFB9A1ED)
    "pentest" -> Color(0xFFDC9BAF)
    "osint" -> Color(0xFF95CBBB)
    "design" -> Color(0xFFD0A4EB)
    "agent" -> Color(0xFF8EB6FF)
    else -> Blue
}

private fun domainIcon(slug: String): ImageVector = when (slug) {
    "code" -> Icons.Outlined.Code
    "pentest" -> Icons.Outlined.GpsFixed
    "osint" -> Icons.Outlined.Search
    "design" -> Icons.Outlined.Palette
    "agent" -> Icons.Outlined.SmartToy
    else -> Icons.Outlined.Settings
}

@Composable
internal fun BrandMark(size: Dp = 32.dp) {
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size * 0.31f)).background(Blue),
        contentAlignment = Alignment.Center,
    ) {
        Text("L", color = Color.White, fontWeight = FontWeight.Bold, fontSize = (size.value * 0.46f).sp)
    }
}

@Composable
internal fun Avatar(letter: String, onClick: () -> Unit) {
    Box(
        Modifier.size(36.dp).clip(CircleShape).background(Blue.copy(alpha = 0.18f)).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(letter, color = Color(0xFF99C9FF), fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
    }
}

@Composable
internal fun Wordmark() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        BrandMark()
        Text("Layla", color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 22.sp, letterSpacing = (-0.4).sp)
    }
}

@Composable
internal fun BackBar(title: String, onBack: () -> Unit, end: @Composable (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        TextButton(onClick = onBack) { Text("Назад", color = Blue) }
        Text(
            title,
            color = Color.White,
            fontWeight = FontWeight.SemiBold,
            fontSize = 20.sp,
            letterSpacing = (-0.3).sp,
            modifier = Modifier.weight(1f).padding(end = 8.dp),
            maxLines = 1,
        )
        end?.invoke()
    }
}

@Composable
internal fun DomainTile(slug: String, title: String, subtitle: String, onClick: () -> Unit) {
    val tint = domainColor(slug)
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card).clickable(onClick = onClick).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(tint.copy(alpha = 0.16f)), contentAlignment = Alignment.Center) {
            Icon(domainIcon(slug), contentDescription = null, tint = tint)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
            Text(subtitle, color = Muted, fontSize = 13.sp, lineHeight = 18.sp)
        }
    }
}

@Composable
internal fun ListTile(title: String, onClick: (() -> Unit)?) {
    val shape = RoundedCornerShape(14.dp)
    Text(
        title,
        color = Color.White,
        fontSize = 16.sp,
        modifier = Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(Card)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 16.dp, vertical = 15.dp),
    )
}

@Composable
internal fun Panel(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Card).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        content = content,
    )
}

@Composable
internal fun Segments(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).clip(RoundedCornerShape(999.dp)).background(Card).padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEach { (value, label) ->
            val on = value == selected
            Text(
                label,
                color = if (on) Color.White else Muted,
                fontSize = 13.sp,
                fontWeight = if (on) FontWeight.SemiBold else FontWeight.Medium,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(if (on) Raised else Color.Transparent)
                    .clickable { onSelect(value) }
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            )
        }
    }
}

@Composable
internal fun ChatBubble(role: String, content: String) {
    val mine = role == "user"
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        if (!mine) BrandMark(26.dp)
        Text(
            content.ifBlank { "…" },
            color = Soft,
            fontSize = 15.sp,
            lineHeight = 22.sp,
            modifier = Modifier
                .padding(start = if (mine) 0.dp else 8.dp)
                .weight(1f, fill = false)
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(18.dp))
                .background(if (mine) Raised else Card)
                .padding(horizontal = 14.dp, vertical = 12.dp),
        )
    }
}
