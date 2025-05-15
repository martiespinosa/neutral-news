//
//  MediaHeadlineView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/4/25.
//

import SwiftUI

struct MediaHeadlineView: View {
    let news: News
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // TODO: Pedir permiso para usar los logos de los medios?
            if let uiImage = UIImage(named: news.sourceMedium.pressMedia.name.normalized()) {
                Image(uiImage: uiImage)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 24)
            } else {
                Text(news.sourceMedium.pressMedia.name)
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
            }
            
            Text(news.title)
                .font(.system(size: 20, design: .serif))
                .fontWeight(.semibold)
            
            Spacer()
            
            BiasScoreView(biasScore: news.neutralScore)
        }
        .padding()  
        .frame(width: 230, height: 230)
        .background(.thinMaterial)
        .clipShape(.rect(cornerRadius: 20))
    }
}

#Preview {
    MediaHeadlineView(news: .mock)
}
